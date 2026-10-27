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
 *
 * [automaticSnapshots] keeps bounded same-device copies of the aggregate ([LandSnapshotStorage]). A
 * copy is written only after the primary write succeeded, and a refused copy never turns a completed
 * save into a reported failure: the land change is already persisted, and the next successful write
 * rotates a fresh copy in. When the primary store cannot be read, the newest fully valid copy is
 * restored and reported through [consumeRecovery]; when no copy is valid the read fails with
 * [LandStoreUnreadableException] instead of opening an empty store.
 *
 * A permanent deletion first writes a durable purge marker, then the primary aggregate, then
 * sanitizes every retained copy. Every read filters the marked ids, so even a copy that could not be
 * rewritten can never bring the land back. Nothing in this class touches a network or a cloud backup
 * destination.
 */
class LandRepository(
    private val storage: LandStorage,
    private val automaticSnapshots: LandSnapshotStorage? = storage as? LandSnapshotStorage,
    private val idGenerator: () -> String = { generateLandId() },
    private val nowEpochMillis: () -> Long = { 0L },
) {
    private var pendingRecovery: LandStoreRecovery? = null

    /** The active lands, in their stored order. Removed lands are never included. */
    fun list(): List<Land> = readSnapshot().active

    /** The removed lands, in removal order. They are not part of [list]. */
    fun listRemoved(): List<RemovedLand> = readSnapshot().removed

    /**
     * The recovery the app has not told the person about yet, consumed so it is announced once.
     *
     * A store read that simply succeeded returns `null`; only a read that rebuilt the primary store
     * from an automatic copy reports anything.
     */
    fun consumeRecovery(): LandStoreRecovery? = pendingRecovery.also { pendingRecovery = null }

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
     *
     * The durable purge marker is written first. If the primary write is then refused, the marker
     * stays and every read keeps filtering that id, so the record can never come back from a stale
     * automatic copy; the person sees a failed write and no copy silently resurrects the land.
     */
    fun permanentlyDelete(id: String): LandLifecycleResult {
        val snapshot = readSnapshot()
        val index = snapshot.removed.indexOfFirst { it.land.id == id }
        if (index < 0) return LandLifecycleResult.Missing
        val land = snapshot.removed[index].land
        val purged = purgedIds() + id
        return try {
            writePurgeMarker(purged)
            val updated = snapshot.copy(
                removed = snapshot.removed.filterIndexed { position, _ -> position != index },
            )
            storage.write(LandStoreFormat.encode(updated))
            recordAutomaticCopy(updated)
            // The marker is cleared only once the primary store and every retained copy are clean.
            // A copy that cannot be rewritten is dropped; if even that fails the marker stays, and
            // the read path keeps filtering it.
            if (sanitizeSnapshots(purged)) clearPurgeMarker()
            LandLifecycleResult.Done(land)
        } catch (_: Exception) {
            LandLifecycleResult.StorageFailed
        }
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
        if (legacy != null) {
            val migrated = LandSnapshot(active = legacy)
            // One-time migration: the aggregate is written before it is returned, and a refused write
            // throws here so the caller reports a failed read and the v1 store keeps its records.
            writeSnapshot(migrated)
            return migrated
        }
        val purged = purgedIds()
        val decoded = LandStoreFormat.decode(stored)
        if (decoded != null) return decoded.withoutIds(purged)
        if (stored == null) {
            // No primary store yet: a first run, not a damaged one. A copy left behind by an earlier
            // install is still recovered below before this is accepted as empty.
            return restoreFromAutomaticCopies(purged) ?: LandSnapshot()
        }
        return restoreFromAutomaticCopies(purged) ?: throw LandStoreUnreadableException()
    }

    /**
     * The newest fully valid automatic copy, already filtered by the purge marker, written back as the
     * primary store. Returns `null` when no copy is valid, so the caller can report a failed read.
     */
    private fun restoreFromAutomaticCopies(purged: Set<String>): LandSnapshot? {
        val copies = automaticSnapshots ?: return null
        val recovered = copies.readSnapshots()
            .firstNotNullOfOrNull { stored -> LandSnapshotFormat.unwrap(stored) }
            ?: return null
        val filtered = recovered.withoutIds(purged)
        // A refused rebuild propagates: the app must not open the store as if it had been recovered.
        storage.write(LandStoreFormat.encode(filtered))
        pendingRecovery = LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY
        recordAutomaticCopy(filtered)
        if (sanitizeSnapshots(purged)) clearPurgeMarker()
        return filtered
    }

    private fun writeSnapshot(snapshot: LandSnapshot) {
        storage.write(LandStoreFormat.encode(snapshot))
        recordAutomaticCopy(snapshot)
    }

    /**
     * Adds one automatic copy of an already written aggregate. A refused copy is not reported as a
     * failed save: the primary store already holds the change, and the next successful write rotates
     * a fresh copy in.
     */
    private fun recordAutomaticCopy(snapshot: LandSnapshot) {
        val copies = automaticSnapshots ?: return
        runCatching {
            copies.writeSnapshot(LandSnapshotFormat.wrap(LandStoreFormat.encode(snapshot)))
        }
    }

    /**
     * Rewrites every retained copy without [excludedIds], dropping copies that are not fully valid,
     * and reports whether the retained set is now clean.
     */
    private fun sanitizeSnapshots(excludedIds: Set<String>): Boolean {
        val copies = automaticSnapshots ?: return true
        return runCatching {
            val sanitized = copies.readSnapshots().mapNotNull { stored ->
                val snapshot = LandSnapshotFormat.unwrap(stored) ?: return@mapNotNull null
                val kept = snapshot.withoutIds(excludedIds)
                if (kept == snapshot) stored else LandSnapshotFormat.wrap(LandStoreFormat.encode(kept))
            }
            copies.replaceSnapshots(sanitized)
            true
        }.getOrDefault(false)
    }

    private fun purgedIds(): Set<String> =
        LandPurgeMarkerFormat.decode(automaticSnapshots?.readPurgeMarker())

    private fun writePurgeMarker(ids: Set<String>) {
        automaticSnapshots?.writePurgeMarker(
            LandPurgeMarkerFormat.encode(ids).ifEmpty { null },
        )
    }

    private fun clearPurgeMarker() {
        runCatching { automaticSnapshots?.writePurgeMarker(null) }
    }

    private fun writeTransition(snapshot: LandSnapshot, land: Land): LandLifecycleResult =
        try {
            writeSnapshot(snapshot)
            LandLifecycleResult.Done(land)
        } catch (_: Exception) {
            LandLifecycleResult.StorageFailed
        }
}

/** The same aggregate without the records a permanent deletion already selected. */
private fun LandSnapshot.withoutIds(ids: Set<String>): LandSnapshot =
    if (ids.isEmpty()) {
        this
    } else {
        copy(
            active = active.filterNot { land -> land.id in ids },
            removed = removed.filterNot { removed -> removed.land.id in ids },
        )
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
