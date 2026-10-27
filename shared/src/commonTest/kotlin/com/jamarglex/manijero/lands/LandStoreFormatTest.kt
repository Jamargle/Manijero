package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * The one current `land-store-v2` aggregate format: one writer, one reader, and the strict
 * `land-store-v1` reader that exists only as the one-time migration input.
 */
class LandStoreFormatTest {
    @Test
    fun `an absent or unknown value is not a current store`() {
        // A damaged or foreign value must never read as an empty aggregate, because that would show
        // the person an empty land list instead of a failed read. Only the two sections read empty.
        assertNull(LandStoreFormat.decode(null))
        assertNull(LandStoreFormat.decode(""))
        assertNull(LandStoreFormat.decode("land-store-v0\nwhatever"))
        assertNull(LandStoreFormat.decode("not a land store"))
    }

    @Test
    fun `a truncated or repeated section marker is not a current store`() {
        assertNull(
            LandStoreFormat.decode("land-store-v2\nactive\nland-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2"),
            "a store that lost its removed marker was truncated, not emptied",
        )
        assertNull(
            LandStoreFormat.decode("land-store-v2\nremoved\nactive"),
            "the aggregate always starts with the active marker",
        )
        assertNull(
            LandStoreFormat.decode("land-store-v2\nactive\nremoved\nremoved"),
            "a repeated removed marker is damage, not a second section",
        )
    }

    @Test
    fun `a complete store reopens and a partially valid copy is rejected whole`() {
        val encoded = """
            land-store-v2
            active
            land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
            land-2|Campos rotos|El Llano||DRYLAND|ORGANIC|NO_EXISTE||1.5|85||3|4
            removed
        """.trimIndent()

        val lenient = LandStoreFormat.decode(encoded)
        assertEquals(listOf("land-1"), lenient?.active?.map { it.id })
        assertNull(
            LandStoreFormat.decode(encoded, requireEveryRecord = true),
            "an automatic copy with any undecodable record is never a complete restore",
        )
        assertEquals(
            LandSnapshot(),
            LandStoreFormat.decode(LandStoreFormat.encode(LandSnapshot()), requireEveryRecord = true),
        )
    }

    @Test
    fun `an empty store is the two sections and reopens empty`() {
        val encoded = LandStoreFormat.encode(LandSnapshot())

        assertEquals("land-store-v2\nactive\nremoved", encoded)
        assertEquals(LandSnapshot(), LandStoreFormat.decode(encoded))
    }

    @Test
    fun `round trip keeps every field of active and removed records including escaped text`() {
        val land = Land(
            id = "land|1",
            name = "Olivar 100%\nNorte",
            zone = "Cañada|del Sur",
            municipality = null,
            waterRegime = WaterRegime.MIXED,
            productionMethod = ProductionMethod.ORGANIC,
            variety = LandVariety.OTHER,
            varietyOther = "Royal, 40",
            areaHectares = 1.5,
            treeCount = 1200,
            notes = "Línea\n2 con 100% y |",
            createdAtEpochMillis = 1_700_000_000_000L,
            updatedAtEpochMillis = 1_700_000_111_111L,
        )
        val removed = land.copy(
            id = "land-2",
            name = "La Loma",
            zone = "La Vega",
            municipality = "Martos",
            variety = LandVariety.PICUAL,
            varietyOther = null,
            areaHectares = 2.5,
            treeCount = null,
            notes = null,
            createdAtEpochMillis = 5,
            updatedAtEpochMillis = 6,
        )
        val snapshot = LandSnapshot(
            active = listOf(land),
            removed = listOf(RemovedLand(removed, 1_700_000_222_222L)),
        )

        val encoded = LandStoreFormat.encode(snapshot)

        assertEquals(snapshot, LandStoreFormat.decode(encoded))
        val activeLine = encoded.lineSequence().toList()[2]
        assertEquals(13, activeLine.split('|').size)
        val removedLine = encoded.lineSequence().toList()[4]
        assertEquals(14, removedLine.split('|').size, "a removed line adds only its removal time")
    }

    @Test
    fun `corrupt records are skipped whole and valid neighbours survive`() {
        val encoded = """
            land-store-v2
            active
            land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
            land-2|Campos rotos|El Llano||DRYLAND|ORGANIC|NO_EXISTE||1.5|85||3|4
            land-3|Línea corta|El Llano||DRYLAND
            land-4|Área mala|La Vega||UNKNOWN|UNKNOWN|UNKNOWN||NaN|||5|6
            land-5|Árboles malos|La Vega||UNKNOWN|UNKNOWN|UNKNOWN||1|x||7|8
            land-6|La Loma|La Vega||IRRIGATED|MIXED|OTHER|Royal|2.5|1200|Nota|9|10
            removed
            land-7|Quitado|El Llano||UNKNOWN|UNKNOWN|UNKNOWN|||||11|12|13
            land-8|Sin hora|El Llano||UNKNOWN|UNKNOWN|UNKNOWN|||||14|15|no-es-hora
            land-9|Quitado también|La Vega||UNKNOWN|UNKNOWN|UNKNOWN|||||16|17|18
        """.trimIndent()

        val snapshot = requireNotNull(LandStoreFormat.decode(encoded))

        assertEquals(listOf("land-1", "land-6"), snapshot.active.map { it.id })
        assertEquals(listOf("land-7", "land-9"), snapshot.removed.map { it.land.id })
        assertEquals(13, snapshot.removed[0].removedAtEpochMillis)
        assertEquals(18, snapshot.removed[1].removedAtEpochMillis)
        assertEquals("PICUAL", snapshot.active[0].variety.name)
        assertNull(snapshot.active[0].municipality)
        assertEquals(1.5, snapshot.active[0].areaHectares)
        assertEquals(85, snapshot.active[0].treeCount)
        assertEquals("Royal", snapshot.active[1].varietyOther)
        assertEquals(2.5, snapshot.active[1].areaHectares)
        assertEquals(1200, snapshot.active[1].treeCount)
        assertEquals("Nota", snapshot.active[1].notes)
    }

    @Test
    fun `a record without a zone is skipped whole`() {
        val encoded = """
            land-store-v2
            active
            land-1|Los Olivos||Martos|UNKNOWN|UNKNOWN|UNKNOWN|||||1|2
            land-2|La Loma|El Llano|Martos|UNKNOWN|UNKNOWN|UNKNOWN|||||3|4
            removed
            land-3|Quitado||Martos|UNKNOWN|UNKNOWN|UNKNOWN|||||5|6|7
        """.trimIndent()

        val snapshot = requireNotNull(LandStoreFormat.decode(encoded))

        assertEquals(listOf("land-2"), snapshot.active.map { it.id })
        assertEquals(emptyList(), snapshot.removed)
    }

    @Test
    fun `a current store with another header reads as no records`() {
        val encoded = """
            land-store-v3
            active
            land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
            removed
        """.trimIndent()

        assertNull(LandStoreFormat.decode(encoded))
    }

    @Test
    fun `a current-format store is not legacy input`() {
        val encoded = LandStoreFormat.encode(
            LandSnapshot(active = listOf(land("land-1", "Los Olivos"))),
        )

        assertNull(LandStoreFormat.decodeLegacy(encoded))
        assertNull(LandStoreFormat.decodeLegacy(null))
        assertNull(LandStoreFormat.decodeLegacy(""))
        assertNull(LandStoreFormat.decodeLegacy("land-store-v0\nwhatever"))
    }

    @Test
    fun `the legacy v1 reader returns every decodable active record and skips corrupt lines`() {
        val encoded = """
            land-store-v1
            land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
            land-2|Campos rotos|El Llano||DRYLAND|ORGANIC|NO_EXISTE||1.5|85||3|4
            land-3|Sin zona||Martos|UNKNOWN|UNKNOWN|UNKNOWN|||||5|6
            land-4|La Loma|La Vega||IRRIGATED|MIXED|OTHER|Royal|2.5|1200|Nota|7|8
        """.trimIndent()

        val lands = LandStoreFormat.decodeLegacy(encoded)

        assertEquals(listOf("land-1", "land-4"), lands?.map { it.id })
        assertEquals("El Llano", lands?.get(0)?.zone)
        assertEquals("Royal", lands?.get(1)?.varietyOther)
    }

    @Test
    fun `a header-only legacy store migrates as an empty list`() {
        assertEquals(emptyList(), LandStoreFormat.decodeLegacy("land-store-v1"))
    }

    @Test
    fun `a v1 header is never read as a current store`() {
        val encoded = """
            land-store-v1
            land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
        """.trimIndent()

        assertNull(LandStoreFormat.decode(encoded))
        assertTrue(LandStoreFormat.decodeLegacy(encoded)?.isNotEmpty() == true)
    }

    private fun land(id: String, name: String): Land = Land(
        id = id,
        name = name,
        zone = "El Llano",
        createdAtEpochMillis = 1,
        updatedAtEpochMillis = 2,
    )
}
