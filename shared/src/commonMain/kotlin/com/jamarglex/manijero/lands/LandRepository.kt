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
            municipality = normalized.municipality,
            waterRegime = normalized.waterRegime,
            productionMethod = normalized.productionMethod,
            areaHectares = normalized.areaHectares,
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
            municipality = normalized.municipality,
            waterRegime = normalized.waterRegime,
            productionMethod = normalized.productionMethod,
            areaHectares = normalized.areaHectares,
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

private fun normalize(draft: LandDraft): LandDraft {
    require(draft.name.trim().isNotEmpty()) { "Land name must not be blank" }
    require(draft.areaHectares == null || draft.areaHectares >= 0.0) {
        "Land area must not be negative"
    }
    return draft.copy(
        name = draft.name.trim(),
        municipality = draft.municipality?.trim()?.ifEmpty { null },
        notes = draft.notes?.trim()?.ifEmpty { null },
    )
}

private fun generateLandId(): String = "land-${Random.nextLong().toString(16)}"

internal object LandStoreFormat {
    private const val HEADER = "land-store-v1"
    private const val SEPARATOR = "|"

    fun encode(records: List<Land>): String = buildString {
        append(HEADER)
        records.forEach { land ->
            append('\n')
            append(listOf(
                land.id, land.name, land.municipality.orEmpty(), land.waterRegime.name,
                land.productionMethod.name, land.areaHectares?.toString().orEmpty(),
                land.notes.orEmpty(), land.createdAtEpochMillis.toString(),
                land.updatedAtEpochMillis.toString(),
            ).joinToString(SEPARATOR, transform = ::escape))
        }
    }

    fun decode(value: String?): List<Land> {
        if (value.isNullOrEmpty()) return emptyList()
        val lines = value.lineSequence().toList()
        if (lines.firstOrNull() != HEADER) return emptyList()
        return lines.drop(1).mapNotNull { line ->
            runCatching {
                val fields = line.split(SEPARATOR).map(::unescape)
                require(fields.size == 9)
                Land(
                    id = fields[0].takeIf(String::isNotEmpty) ?: return@runCatching null,
                    name = fields[1].takeIf(String::isNotEmpty) ?: return@runCatching null,
                    municipality = fields[2].ifEmpty { null },
                    waterRegime = WaterRegime.valueOf(fields[3]),
                    productionMethod = ProductionMethod.valueOf(fields[4]),
                    areaHectares = fields[5].ifEmpty { null }?.toDouble(),
                    notes = fields[6].ifEmpty { null },
                    createdAtEpochMillis = fields[7].toLong(),
                    updatedAtEpochMillis = fields[8].toLong(),
                )
            }.getOrNull()
        }
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
