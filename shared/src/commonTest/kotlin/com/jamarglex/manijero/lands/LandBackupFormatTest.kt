package com.jamarglex.manijero.lands

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

/**
 * The portable backup file contract. `commonTest` runs on the JVM (Desktop) and on the Android host,
 * so the pinned [CROSS_PLATFORM_FIXTURE] proves both platforms write and read the same bytes.
 */
class LandBackupFormatTest {
    @Test
    fun `a round trip keeps both lists, their order and every supported value`() {
        val snapshot = sampleSnapshot()

        val decoded = LandBackupFormat.decode(LandBackupFormat.encode(snapshot))

        assertEquals(LandBackupDecodeResult.Valid(snapshot), decoded)
    }

    @Test
    fun `an empty store round trips to an empty backup`() {
        assertEquals(
            LandBackupDecodeResult.Valid(LandSnapshot()),
            LandBackupFormat.decode(LandBackupFormat.encode(LandSnapshot())),
        )
    }

    @Test
    fun `the pinned cross-platform fixture is written and read byte for byte`() {
        assertEquals(CROSS_PLATFORM_FIXTURE, LandBackupFormat.encode(fixtureSnapshot()))
        assertEquals(
            LandBackupDecodeResult.Valid(fixtureSnapshot()),
            LandBackupFormat.decode(CROSS_PLATFORM_FIXTURE),
        )
    }

    @Test
    fun `the file holds only the format header and land values`() {
        val root = Json.parseToJsonElement(LandBackupFormat.encode(sampleSnapshot())).jsonObject
        assertEquals(setOf("format", "version", "checksum", "lands"), root.keys)
        val lands = root.getValue("lands").jsonObject
        assertEquals(setOf("active", "removed"), lands.keys)
        val landKeys = setOf(
            "id", "name", "zone", "municipality", "waterRegime", "productionMethod", "variety",
            "varietyOther", "areaHectares", "treeCount", "notes", "createdAtEpochMillis",
            "updatedAtEpochMillis",
        )
        lands.getValue("active").jsonArray.forEach { land ->
            assertEquals(true, landKeys.containsAll((land as JsonObject).keys))
        }
        lands.getValue("removed").jsonArray.forEach { removed ->
            assertEquals(setOf("land", "removedAtEpochMillis"), removed.jsonObject.keys)
            assertEquals(true, landKeys.containsAll(removed.jsonObject.getValue("land").jsonObject.keys))
        }
    }

    @Test
    fun `an absent optional value is omitted instead of written as zero or empty`() {
        val text = LandBackupFormat.encode(LandSnapshot(active = listOf(land("a", "Sin datos"))))
        val active = Json.parseToJsonElement(text).jsonObject.getValue("lands").jsonObject
            .getValue("active").jsonArray.single().jsonObject
        listOf("municipality", "varietyOther", "areaHectares", "treeCount", "notes").forEach { key ->
            assertEquals(false, key in active, "$key must be omitted when absent")
        }
    }

    @Test
    fun `formatting and a byte order mark do not change a valid file`() {
        val pretty = LandBackupFormat.encode(sampleSnapshot())
        val compact = Json.encodeToString(JsonObject.serializer(), Json.parseToJsonElement(pretty).jsonObject)
        assertIs<LandBackupDecodeResult.Valid>(LandBackupFormat.decode(compact))
        assertIs<LandBackupDecodeResult.Valid>(LandBackupFormat.decode("﻿" + pretty))
        assertIs<LandBackupDecodeResult.Valid>(LandBackupFormat.decode(pretty.replace("\n", "\r\n")))
    }

    @Test
    fun `a file that is not a backup is refused as such`() {
        listOf(
            "",
            "hola, esto es una nota",
            "[1, 2, 3]",
            """{"format": "otra-app", "version": 1}""",
            """{"version": 1, "lands": {"active": [], "removed": []}}""",
        ).forEach { text -> assertProblem(LandBackupProblem.NOT_A_BACKUP, text) }
    }

    @Test
    fun `another format version is refused before its contents are read`() {
        val lands = LandBackupFormat.portable(sampleSnapshot())
        assertProblem(LandBackupProblem.UNSUPPORTED_VERSION, LandBackupFormat.encodeFile(lands, version = 2))
        assertProblem(LandBackupProblem.UNSUPPORTED_VERSION, LandBackupFormat.encodeFile(lands, version = 0))
        assertProblem(
            LandBackupProblem.DAMAGED,
            LandBackupFormat.encode(sampleSnapshot()).replace("\"version\": 1", "\"version\": \"1\""),
        )
    }

    @Test
    fun `a truncated, altered or reshaped file is refused as damaged`() {
        val valid = LandBackupFormat.encode(sampleSnapshot())
        assertProblem(LandBackupProblem.DAMAGED, valid.substring(0, valid.length / 2))
        assertProblem(LandBackupProblem.DAMAGED, valid.replace("Los Olivos", "Los Almendros"))
        assertProblem(LandBackupProblem.DAMAGED, valid.replace("\"checksum\": \"fnv1a64:", "\"checksum\": \"fnv1a64:0"))
        assertProblem(
            LandBackupProblem.DAMAGED,
            valid.replace("\"zone\": \"El Llano\"", "\"zone\": \"El Llano\", \"deviceId\": \"abc\""),
        )
        assertProblem(LandBackupProblem.DAMAGED, valid.replace("\"removedAtEpochMillis\"", "\"removedAt\""))
        assertProblem(LandBackupProblem.DAMAGED, valid.replace("\"treeCount\": 85", "\"treeCount\": 8.5"))
        // A non-finite surface cannot even be written as JSON; the strict reader refuses the literal.
        assertProblem(LandBackupProblem.DAMAGED, valid.replace("\"areaHectares\": 1.5", "\"areaHectares\": NaN"))
        assertProblem(LandBackupProblem.DAMAGED, valid.replace("\"areaHectares\": 1.5", "\"areaHectares\": Infinity"))
    }

    @Test
    fun `well-formed records that break a land rule are refused whole`() {
        val good = land("a", "Los Olivos")
        listOf(
            good.copy(id = ""),
            good.copy(name = ""),
            good.copy(zone = "   "),
            good.copy(areaHectares = -1.0),
            good.copy(treeCount = 0),
            good.copy(variety = LandVariety.OTHER, varietyOther = null),
            good.copy(variety = LandVariety.PICUAL, varietyOther = "Sobra"),
            good.copy(municipality = ""),
            good.copy(notes = ""),
        ).forEach { broken ->
            val lands = LandBackupFormat.portable(
                LandSnapshot(active = listOf(land("ok", "Bien")), removed = listOf(RemovedLand(broken, 1))),
            )
            assertProblem(LandBackupProblem.INVALID_CONTENT, LandBackupFormat.encodeFile(lands), "$broken")
        }

        val unknownEnum = LandBackupFormat.portable(LandSnapshot(active = listOf(good)))
            .let { it.copy(active = listOf(it.active.single().copy(waterRegime = "GOTEO"))) }
        assertProblem(LandBackupProblem.INVALID_CONTENT, LandBackupFormat.encodeFile(unknownEnum))
    }

    @Test
    fun `an id repeated within or across the two lists is refused`() {
        val first = land("same", "Uno")
        val second = land("same", "Dos")
        assertProblem(
            LandBackupProblem.INVALID_CONTENT,
            LandBackupFormat.encodeFile(LandBackupFormat.portable(LandSnapshot(active = listOf(first, second)))),
        )
        assertProblem(
            LandBackupProblem.INVALID_CONTENT,
            LandBackupFormat.encodeFile(
                LandBackupFormat.portable(
                    LandSnapshot(active = listOf(first), removed = listOf(RemovedLand(second, 3))),
                ),
            ),
        )
    }

    @Test
    fun `an oversized file is refused before it is parsed`() {
        assertProblem(LandBackupProblem.TOO_LARGE, " ".repeat(MAX_LAND_BACKUP_BYTES + 1))
        assertIs<LandBackupOpenResult.TooLarge>(landBackupOpenResultFromBytes(ByteArray(MAX_LAND_BACKUP_BYTES + 1)))
        assertIs<LandBackupOpenResult.Failed>(landBackupOpenResultFromBytes(byteArrayOf(0xC3.toByte(), 0x28)))
        assertEquals(
            LandBackupOpenResult.Opened("Úbeda"),
            landBackupOpenResultFromBytes("Úbeda".encodeToByteArray()),
        )
    }

    private fun assertProblem(expected: LandBackupProblem, text: String, message: String? = null) {
        assertEquals(LandBackupDecodeResult.Invalid(expected), LandBackupFormat.decode(text), message)
    }
}

private fun land(id: String, name: String) = Land(
    id = id,
    name = name,
    zone = "El Llano",
    createdAtEpochMillis = 10,
    updatedAtEpochMillis = 20,
)

private fun sampleSnapshot() = LandSnapshot(
    active = listOf(
        Land(
            id = "land-1",
            name = "Los Olivos",
            zone = "El Llano",
            municipality = "Martos",
            waterRegime = WaterRegime.DRYLAND,
            productionMethod = ProductionMethod.ORGANIC,
            variety = LandVariety.PICUAL,
            areaHectares = 1.5,
            treeCount = 85,
            notes = "Linde con el arroyo | \"ojo\"\nsegunda línea",
            createdAtEpochMillis = 1_700_000_000_000,
            updatedAtEpochMillis = 1_700_000_100_000,
        ),
        land("land-2", "La Loma"),
    ),
    removed = listOf(
        RemovedLand(
            Land(
                id = "land-3",
                name = "El Cerro",
                zone = "Camino viejo",
                variety = LandVariety.OTHER,
                varietyOther = "Royal de Cazorla",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.MIXED,
                areaHectares = 0.0,
                treeCount = 1,
                createdAtEpochMillis = 5,
                updatedAtEpochMillis = 6,
            ),
            removedAtEpochMillis = 7,
        ),
        RemovedLand(land("land-4", "Ñora"), removedAtEpochMillis = 8),
    ),
)

private fun fixtureSnapshot() = LandSnapshot(
    active = listOf(
        Land(
            id = "land-a",
            name = "Los Olivos",
            zone = "El Llano",
            municipality = "Úbeda",
            waterRegime = WaterRegime.MIXED,
            productionMethod = ProductionMethod.CONVENTIONAL,
            variety = LandVariety.HOJIBLANCA,
            areaHectares = 12.75,
            treeCount = 1250,
            notes = "Nota con acento",
            createdAtEpochMillis = 1,
            updatedAtEpochMillis = 2,
        ),
    ),
    removed = listOf(
        RemovedLand(
            Land(
                id = "land-b",
                name = "La Loma",
                zone = "Linde del arroyo",
                createdAtEpochMillis = 3,
                updatedAtEpochMillis = 4,
            ),
            removedAtEpochMillis = 5,
        ),
    ),
)

// Written once by the encoder and pinned: a change here is a portable-format change, not a refactor.
private val CROSS_PLATFORM_FIXTURE = """{
    "format": "manijero-land-backup",
    "version": 1,
    "checksum": "fnv1a64:4b939261b9288b69",
    "lands": {
        "active": [
            {
                "id": "land-a",
                "name": "Los Olivos",
                "zone": "El Llano",
                "municipality": "Úbeda",
                "waterRegime": "MIXED",
                "productionMethod": "CONVENTIONAL",
                "variety": "HOJIBLANCA",
                "areaHectares": 12.75,
                "treeCount": 1250,
                "notes": "Nota con acento",
                "createdAtEpochMillis": 1,
                "updatedAtEpochMillis": 2
            }
        ],
        "removed": [
            {
                "land": {
                    "id": "land-b",
                    "name": "La Loma",
                    "zone": "Linde del arroyo",
                    "waterRegime": "UNKNOWN",
                    "productionMethod": "UNKNOWN",
                    "variety": "UNKNOWN",
                    "createdAtEpochMillis": 3,
                    "updatedAtEpochMillis": 4
                },
                "removedAtEpochMillis": 5
            }
        ]
    }
}
"""
