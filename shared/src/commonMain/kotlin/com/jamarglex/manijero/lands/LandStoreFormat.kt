package com.jamarglex.manijero.lands

/**
 * The local land store: one versioned aggregate with an active section and a removed section.
 *
 * Current format (`land-store-v2`):
 *
 * ```text
 * land-store-v2
 * active
 * id|name|zone|municipality|waterRegime|productionMethod|variety|varietyOther|areaHectares|treeCount|notes|createdAt|updatedAt
 * removed
 * id|name|zone|municipality|waterRegime|productionMethod|variety|varietyOther|areaHectares|treeCount|notes|createdAt|updatedAt|removedAt
 * ```
 *
 * Both section markers are always written, so an empty store is the three header lines and a reader
 * can tell a complete aggregate from a truncated one. A record line that cannot be decoded is skipped
 * whole; a store with an unrecognised header yields no records.
 *
 * [decode] reads only this current format. [decodeLegacy] reads the pre-lifecycle `land-store-v1`
 * snapshot — the old 13-field lines after that header — as the **one-time migration input**; a v1
 * store is never read as a current store, so after migration there is exactly one live decoder.
 */
internal object LandStoreFormat {
    private const val HEADER = "land-store-v2"
    private const val LEGACY_HEADER = "land-store-v1"
    private const val ACTIVE_SECTION = "active"
    private const val REMOVED_SECTION = "removed"
    private const val SEPARATOR = "|"
    private const val FIELD_COUNT = 13
    private const val REMOVED_FIELD_COUNT = FIELD_COUNT + 1

    fun encode(snapshot: LandSnapshot): String = buildString {
        append(HEADER)
        append('\n')
        append(ACTIVE_SECTION)
        snapshot.active.forEach { land ->
            append('\n')
            append(encodeLine(landFields(land)))
        }
        append('\n')
        append(REMOVED_SECTION)
        snapshot.removed.forEach { removed ->
            append('\n')
            append(
                encodeLine(landFields(removed.land) + removed.removedAtEpochMillis.toString()),
            )
        }
    }

    fun decode(value: String?): LandSnapshot {
        if (value.isNullOrEmpty()) return LandSnapshot()
        val lines = value.lineSequence().toList()
        if (lines.firstOrNull() != HEADER) return LandSnapshot()
        val body = lines.drop(1)
        if (body.firstOrNull() != ACTIVE_SECTION) return LandSnapshot()
        val removedStart = body.indexOf(REMOVED_SECTION)
        val activeLines = if (removedStart < 0) body.drop(1) else body.subList(1, removedStart)
        val removedLines = if (removedStart < 0) {
            emptyList()
        } else {
            body.subList(removedStart + 1, body.size)
        }
        return LandSnapshot(
            active = activeLines.mapNotNull(::decodeLand),
            removed = removedLines.mapNotNull(::decodeRemoved),
        )
    }

    /**
     * The old active-only snapshot, or `null` when [value] is not a v1 store. Returning `null` is what
     * keeps this a migration input: only a store that still carries the v1 header is decoded this way.
     */
    fun decodeLegacy(value: String?): List<Land>? {
        if (value.isNullOrEmpty()) return null
        val lines = value.lineSequence().toList()
        if (lines.firstOrNull() != LEGACY_HEADER) return null
        return lines.drop(1).mapNotNull(::decodeLand)
    }

    private fun encodeLine(fields: List<String>): String =
        fields.joinToString(SEPARATOR, transform = ::escape)

    private fun decodeLand(line: String): Land? = runCatching {
        val fields = line.split(SEPARATOR).map(::unescape)
        require(fields.size == FIELD_COUNT)
        decodeFields(fields)
    }.getOrNull()

    private fun decodeRemoved(line: String): RemovedLand? = runCatching {
        val fields = line.split(SEPARATOR).map(::unescape)
        require(fields.size == REMOVED_FIELD_COUNT)
        val land = decodeFields(fields.take(FIELD_COUNT)) ?: return null
        RemovedLand(land = land, removedAtEpochMillis = fields[FIELD_COUNT].toLong())
    }.getOrNull()

    private fun landFields(land: Land): List<String> = listOf(
        land.id,
        land.name,
        land.zone,
        land.municipality.orEmpty(),
        land.waterRegime.name,
        land.productionMethod.name,
        land.variety.name,
        land.varietyOther.orEmpty(),
        land.areaHectares?.toString().orEmpty(),
        land.treeCount?.toString().orEmpty(),
        land.notes.orEmpty(),
        land.createdAtEpochMillis.toString(),
        land.updatedAtEpochMillis.toString(),
    )

    @Suppress("LongParameterList")
    private fun decodeFields(fields: List<String>): Land? {
        val id = fields[0]
        val name = fields[1]
        val zone = fields[2]
        if (id.isEmpty() || name.isEmpty() || zone.isBlank()) return null
        val areaHectares = fields[8].ifEmpty { null }?.toDouble()
        // A record whose stored area is not finite is corrupt whole, never a value to guess.
        if (areaHectares != null && !areaHectares.isFinite()) return null
        return Land(
            id = id,
            name = name,
            zone = zone,
            municipality = fields[3].ifEmpty { null },
            waterRegime = WaterRegime.valueOf(fields[4]),
            productionMethod = ProductionMethod.valueOf(fields[5]),
            variety = LandVariety.valueOf(fields[6]),
            varietyOther = fields[7].ifEmpty { null },
            areaHectares = areaHectares,
            treeCount = fields[9].ifEmpty { null }?.toInt(),
            notes = fields[10].ifEmpty { null },
            createdAtEpochMillis = fields[11].toLong(),
            updatedAtEpochMillis = fields[12].toLong(),
        )
    }

    private fun escape(value: String): String = value
        .replace("%", "%25")
        .replace(SEPARATOR, "%7C")
        .replace("\n", "%0A")
        .replace("\r", "%0D")

    private fun unescape(value: String): String = value
        .replace("%0D", "\r")
        .replace("%0A", "\n")
        .replace("%7C", SEPARATOR)
        .replace("%25", "%")
}
