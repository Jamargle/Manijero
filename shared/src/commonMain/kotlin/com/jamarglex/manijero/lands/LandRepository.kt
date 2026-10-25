package com.jamarglex.manijero.lands

import kotlin.random.Random

interface LandStorage {
    fun read(): String?
    fun write(value: String)
}

class LandRepository(
    private val storage: LandStorage,
    private val idGenerator: () -> String = { generateLandId() },
    private val nowEpochMillis: () -> Long = { 0L },
) {
    fun list(): List<Land> = readRecords()

    fun create(draft: LandDraft, now: Long = nowEpochMillis()): Land {
        val normalized = normalize(draft)
        val existing = readRecords()
        val land = Land(
            id = uniqueId(existing),
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
        writeRecords(existing + land)
        return land
    }

    fun update(id: String, draft: LandDraft, now: Long = nowEpochMillis()): Land? {
        val normalized = normalize(draft)
        val records = readRecords()
        val index = records.indexOfFirst { it.id == id }
        if (index < 0) return null
        val old = records[index]
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
        writeRecords(records.toMutableList().also { it[index] = updated })
        return updated
    }

    fun delete(id: String): Boolean {
        val records = readRecords()
        val remaining = records.filterNot { it.id == id }
        if (remaining.size == records.size) return false
        writeRecords(remaining)
        return true
    }

    private fun uniqueId(existing: List<Land>): String {
        var id = idGenerator()
        while (existing.any { it.id == id }) id = idGenerator()
        return id
    }

    private fun readRecords(): List<Land> = LandStoreFormat.decode(storage.read())

    private fun writeRecords(records: List<Land>) {
        storage.write(LandStoreFormat.encode(records))
    }
}

/**
 * The single write gate: no record is persisted unless every required value is present and every
 * optional value is either absent or valid. The zone is required here (a `LandDraft` cannot even be
 * built without one); a legacy record keeps its empty value only until it is edited.
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

/**
 * The device-local land store.
 *
 * The writer always emits `land-store-v2` with 13 `|`-separated, escaped fields:
 * `id|name|zone|municipality|waterRegime|productionMethod|variety|varietyOther|areaHectares|treeCount|notes|createdAt|updatedAt`.
 * The reader still accepts a `land-store-v1` file (nine fields, no zone/variety/measures) and maps
 * those missing values to `null`/`UNKNOWN`; it never invents a value. A corrupt line is skipped whole,
 * as before, and an unknown header reads as no records.
 */
internal object LandStoreFormat {
    private const val HEADER_V1 = "land-store-v1"
    private const val HEADER_V2 = "land-store-v2"
    private const val SEPARATOR = "|"
    private const val V1_FIELD_COUNT = 9
    private const val V2_FIELD_COUNT = 13

    fun encode(records: List<Land>): String = buildString {
        append(HEADER_V2)
        records.forEach { land ->
            append('\n')
            append(listOf(
                land.id,
                land.name,
                land.zone.orEmpty(),
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
            ).joinToString(SEPARATOR, transform = ::escape))
        }
    }

    fun decode(value: String?): List<Land> {
        if (value.isNullOrEmpty()) return emptyList()
        val lines = value.lineSequence().toList()
        return when (lines.firstOrNull()) {
            HEADER_V1 -> lines.drop(1).mapNotNull(::decodeV1)
            HEADER_V2 -> lines.drop(1).mapNotNull(::decodeV2)
            else -> emptyList()
        }
    }

    private fun decodeV1(line: String): Land? = runCatching {
        val fields = line.split(SEPARATOR).map(::unescape)
        require(fields.size == V1_FIELD_COUNT)
        land(
            id = fields[0],
            name = fields[1],
            zone = null,
            municipality = fields[2].ifEmpty { null },
            waterRegime = fields[3],
            productionMethod = fields[4],
            variety = LandVariety.UNKNOWN.name,
            varietyOther = null,
            areaHectares = fields[5].ifEmpty { null }?.toDouble(),
            treeCount = null,
            notes = fields[6].ifEmpty { null },
            createdAtEpochMillis = fields[7].toLong(),
            updatedAtEpochMillis = fields[8].toLong(),
        )
    }.getOrNull()

    private fun decodeV2(line: String): Land? = runCatching {
        val fields = line.split(SEPARATOR).map(::unescape)
        require(fields.size == V2_FIELD_COUNT)
        land(
            id = fields[0],
            name = fields[1],
            zone = fields[2].ifEmpty { null },
            municipality = fields[3].ifEmpty { null },
            waterRegime = fields[4],
            productionMethod = fields[5],
            variety = fields[6],
            varietyOther = fields[7].ifEmpty { null },
            areaHectares = fields[8].ifEmpty { null }?.toDouble(),
            treeCount = fields[9].ifEmpty { null }?.toInt(),
            notes = fields[10].ifEmpty { null },
            createdAtEpochMillis = fields[11].toLong(),
            updatedAtEpochMillis = fields[12].toLong(),
        )
    }.getOrNull()

    @Suppress("LongParameterList")
    private fun land(
        id: String,
        name: String,
        zone: String?,
        municipality: String?,
        waterRegime: String,
        productionMethod: String,
        variety: String,
        varietyOther: String?,
        areaHectares: Double?,
        treeCount: Int?,
        notes: String?,
        createdAtEpochMillis: Long,
        updatedAtEpochMillis: Long,
    ): Land? {
        if (id.isEmpty() || name.isEmpty()) return null
        // A record whose stored area is not finite is corrupt whole, never a value to guess.
        if (areaHectares != null && !areaHectares.isFinite()) return null
        return Land(
            id = id,
            name = name,
            zone = zone,
            municipality = municipality,
            waterRegime = WaterRegime.valueOf(waterRegime),
            productionMethod = ProductionMethod.valueOf(productionMethod),
            variety = LandVariety.valueOf(variety),
            varietyOther = varietyOther,
            areaHectares = areaHectares,
            treeCount = treeCount,
            notes = notes,
            createdAtEpochMillis = createdAtEpochMillis,
            updatedAtEpochMillis = updatedAtEpochMillis,
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
