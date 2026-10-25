package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** The one `land-store-v1` format: one writer, one reader, and no older shape to migrate. */
class LandStoreFormatTest {
    @Test
    fun `empty and unknown stores read as no records`() {
        assertEquals(emptyList(), LandStoreFormat.decode(null))
        assertEquals(emptyList(), LandStoreFormat.decode(""))
        assertEquals(emptyList(), LandStoreFormat.decode("land-store-v0\nwhatever"))
        assertEquals(emptyList(), LandStoreFormat.decode("not a land store"))
    }

    @Test
    fun `an empty store is just the header and reopens empty`() {
        val encoded = LandStoreFormat.encode(emptyList())
        assertEquals("land-store-v1", encoded)
        assertEquals(emptyList(), LandStoreFormat.decode(encoded))
    }

    @Test
    fun `round trip keeps every field including escaped text`() {
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

        val encoded = LandStoreFormat.encode(listOf(land))

        assertTrue(encoded.startsWith("land-store-v1\n"))
        assertEquals(listOf(land), LandStoreFormat.decode(encoded))
        assertEquals(13, encoded.lineSequence().drop(1).single().split('|').size)
    }

    @Test
    fun `corrupt records are skipped whole and valid neighbours survive`() {
        val encoded = """
            land-store-v1
            land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
            land-2|Campos rotos|El Llano||DRYLAND|ORGANIC|NO_EXISTE||1.5|85||3|4
            land-3|Línea corta|El Llano||DRYLAND
            land-4|Área mala|La Vega||UNKNOWN|UNKNOWN|UNKNOWN||NaN|||5|6
            land-5|Árboles malos|La Vega||UNKNOWN|UNKNOWN|UNKNOWN||1|x||7|8
            land-6|La Loma|La Vega||IRRIGATED|MIXED|OTHER|Royal|2.5|1200|Nota|9|10
        """.trimIndent()

        val lands = LandStoreFormat.decode(encoded)

        assertEquals(listOf("land-1", "land-6"), lands.map { it.id })
        assertEquals("PICUAL", lands[0].variety.name)
        assertNull(lands[0].municipality)
        assertEquals(1.5, lands[0].areaHectares)
        assertEquals(85, lands[0].treeCount)
        assertEquals("Royal", lands[1].varietyOther)
        assertEquals(2.5, lands[1].areaHectares)
        assertEquals(1200, lands[1].treeCount)
        assertEquals("Nota", lands[1].notes)
    }

    @Test
    fun `a record without a zone is skipped whole`() {
        val encoded = """
            land-store-v1
            land-1|Los Olivos||Martos|UNKNOWN|UNKNOWN|UNKNOWN|||||1|2
            land-2|La Loma|El Llano|Martos|UNKNOWN|UNKNOWN|UNKNOWN|||||3|4
        """.trimIndent()

        assertEquals(listOf("land-2"), LandStoreFormat.decode(encoded).map { it.id })
    }

    @Test
    fun `a store with another header reads as no records`() {
        val encoded = """
            land-store-v2
            land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
        """.trimIndent()

        assertEquals(emptyList(), LandStoreFormat.decode(encoded))
    }
}
