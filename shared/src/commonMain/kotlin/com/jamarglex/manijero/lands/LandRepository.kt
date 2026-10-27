package com.jamarglex.manijero.lands

import kotlin.random.Random

interface LandStorage {
    fun read(): String?
    fun write(value: String)
}

/**
 * The local land store: one aggregate of active lands and removed lands.
 *
 * [list] and [listRemoved] are the only read paths, and each returns its own side of one
 * [LandSnapshot]. [list] never returns a removed record, so the land list, the clarification chooser,
 * and every question context keep seeing exactly the lands the person is still using.
 *
 * Every write replaces the whole aggregate with one encoded snapshot: no operation leaves a half
 * updated store. [moveToRemoved], [restore], and [permanentlyDelete] are the lifecycle transitions and
 * each reports a [LandLifecycleResult], so a missing record and a refused write are never presented as
 * a successful move. [create] and [update] keep their accepted behavior, including throwing when the
 * device refuses the write.
 *
 * The store holds the current aggregate format written by [LandStoreFormat]. An existing
 * `land-store-v1` snapshot is read once as migration input: every decoded record becomes an active land
 * and the aggregate is written back before that read returns it, so the old shape never becomes a
 * second ongoing read or write path. A refused migration write propagates, so the person sees a failed
 * read and the old store stays untouched instead of being silently replaced.
 */
class LandRepository(
    private val storage: LandStorage,
    private val idGenerator: () -> String = { generateLandId() },
    private val nowEpochMillis: () -> Long = { 0L },
) {
    /** The active lands, in their stored order. Removed lands are never included. */
    fun list(): List<Land> = readSnapshot().active

    /** The removed lands, in removal order. They are not part of [list]. */
    fun listRemoved(): List<RemovedLand> = readSnapshot().removed

    fun create(draft: LandDraft, now: Long = nowEpochMillis()): Land {
        val normalized = normalize(draft)
        val snapshot = readSnapshot()
        val land = Land(
            id = uniqueId(snapshot),
            name = normalized.name,
            zone = normalized.zone,
            municipality = normalized.municipality,
            waterRegime = normalized.waterRegime,
            productionMethod = normalized.productionMethod,
            variety = normalized.variety,
            varietyOther = normalized.varietyOther,
            areaHectares = normalized.areaHectares,
            treeCount = normalized.treeCount,
            notes = normalized.notes,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )
        writeSnapshot(snapshot.copy(active = snapshot.active + land))
        return land
    }

    fun update(id: String, draft: LandDraft, now: Long = nowEpochMillis()): Land? {
        val normalized = normalize(draft)
        val snapshot = readSnapshot()
        val index = snapshot.active.indexOfFirst { it.id == id }
        if (index < 0) return null
        val old = snapshot.active[index]
        val updated = old.copy(
            name = normalized.name,
            zone = normalized.zone,
            municipality = normalized.municipality,
            waterRegime = normalized.waterRegime,
            productionMethod = normalized.productionMethod,
            variety = normalized.variety,
            varietyOther = normalized.varietyOther,
            areaHectares = normalized.areaHectares,
            treeCount = normalized.treeCount,
            notes = normalized.notes,
            updatedAtEpochMillis = now,
        )
        writeSnapshot(snapshot.copy(active = snapshot.active.toMutableList().also { it[index] = updated }))
        return updated
    }

    /**
     * Moves exactly the active record [id] to the removed list, preserving every stored field and the
     * order of the other active lands. The removed list keeps removal order, so the newest removal is
     * the last one.
     */
    fun moveToRemoved(id: String, now: Long = nowEpochMillis()): LandLifecycleResult {
        val snapshot = readSnapshot()
        val index = snapshot.active.indexOfFirst { it.id == id }
        if (index < 0) return LandLifecycleResult.Missing
        val land = snapshot.active[index]
        return writeTransition(
            snapshot.copy(
                active = snapshot.active.filterIndexed { position, _ -> position != index },
                removed = snapshot.removed + RemovedLand(land, now),
            ),
            land,
        )
    }

    /**
     * Returns exactly the removed record [id] to the **end** of the active list with every stored field
     * unchanged. The other active and removed lands keep their order.
     */
    fun restore(id: String): LandLifecycleResult {
        val snapshot = readSnapshot()
        val index = snapshot.removed.indexOfFirst { it.land.id == id }
        if (index < 0) return LandLifecycleResult.Missing
        val land = snapshot.removed[index].land
        return writeTransition(
            snapshot.copy(
                active = snapshot.active + land,
                removed = snapshot.removed.filterIndexed { position, _ -> position != index },
            ),
            land,
        )
    }

    /**
     * Removes exactly the removed record [id] from the store for good. An active id is not a removal
     * target, so it reports [LandLifecycleResult.Missing] and writes nothing: permanent deletion only
     * ever follows a record the person first moved out of `Mis terrenos`.
     */
    fun permanentlyDelete(id: String): LandLifecycleResult {
        val snapshot = readSnapshot()
        val index = snapshot.removed.indexOfFirst { it.land.id == id }
        if (index < 0) return LandLifecycleResult.Missing
        val land = snapshot.removed[index].land
        return writeTransition(
            snapshot.copy(
                removed = snapshot.removed.filterIndexed { position, _ -> position != index },
            ),
            land,
        )
    }

    private fun uniqueId(snapshot: LandSnapshot): String {
        val taken = snapshot.active.map { it.id } + snapshot.removed.map { it.land.id }
        var id = idGenerator()
        while (id in taken) id = idGenerator()
        return id
    }

    private fun readSnapshot(): LandSnapshot {
        val stored = storage.read()
        val legacy = LandStoreFormat.decodeLegacy(stored)
        if (legacy == null) return LandStoreFormat.decode(stored)
        val migrated = LandSnapshot(active = legacy)
        // One-time migration: the aggregate is written before it is returned, and a refused write
        // throws here so the caller reports a failed read and the v1 store keeps its records.
        writeSnapshot(migrated)
        return migrated
    }

    private fun writeSnapshot(snapshot: LandSnapshot) {
        storage.write(LandStoreFormat.encode(snapshot))
    }

    private fun writeTransition(snapshot: LandSnapshot, land: Land): LandLifecycleResult =
        try {
            writeSnapshot(snapshot)
            LandLifecycleResult.Done(land)
        } catch (_: Exception) {
            LandLifecycleResult.StorageFailed
        }
}

/**
 * The single write gate: no record is persisted unless every required value is present and every
 * optional value is either absent or valid. The zone is required here, as it is in [LandDraft].
 */
private fun normalize(draft: LandDraft): LandDraft {
    require(draft.name.trim().isNotEmpty()) { "Land name must not be blank" }
    require(isValidZone(draft.zone)) { "Land zone must not be blank and must fit the limit" }
    val varietyOther = normalizedVarietyOther(draft.variety, draft.varietyOther)
    require(isValidVarietyOther(draft.variety, draft.varietyOther.orEmpty())) {
        "A custom variety needs its own text"
    }
    val area = draft.areaHectares
    require(area == null || (area.isFinite() && area >= 0.0)) {
        "Land area must be finite and not negative"
    }
    val treeCount = draft.treeCount
    require(treeCount == null || treeCount >= 1) {
        "Land tree count must be at least one"
    }
    return draft.copy(
        name = draft.name.trim(),
        zone = draft.zone.trim(),
        municipality = draft.municipality?.trim()?.ifEmpty { null },
        varietyOther = varietyOther,
        areaHectares = area?.let(::roundHectares),
        notes = draft.notes?.trim()?.ifEmpty { null },
    )
}

private fun generateLandId(): String = "land-${Random.nextLong().toString(16)}"
