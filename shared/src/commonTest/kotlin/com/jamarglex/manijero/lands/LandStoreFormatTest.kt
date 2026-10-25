package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/** The `land-store-v2` writer and the still-supported `land-store-v1` reader. */
class LandStoreFormatTest {
    @Test
    fun `empty and unknown stores read as no records`() {
        assertEquals(emptyList(), LandStoreFormat.decode(null))
        assertEquals(emptyList(), LandStoreFormat.decode(""))
        assertEquals(emptyList(), LandStoreFormat.decode("land-store-v0\nwhatever"))
        assertEquals(emptyList(), LandStoreFormat.decode("not a land store"))
    }

    @Test
    fun `an empty store is a v2 header and a reopened empty store`() {
        val encoded = LandStoreFormat.encode(emptyList())
        assertEquals("land-store-v2", encoded)
        assertEquals(emptyList(), LandStoreFormat.decode(encoded))
    }

    @Test
    fun `v2 round trip keeps every field including escaped text`() {
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

        assertTrue(encoded.startsWith("land-store-v2\n"))
        assertEquals(listOf(land), LandStoreFormat.decode(encoded))
        assertEquals(13, encoded.lineSequence().drop(1).single().split('|').size)
    }

    @Test
    fun `a v1 store still loads without inventing the missing values`() {
        val encoded = """
            land-store-v1
            land-1|Los Olivos|Martos|IRRIGATED|ORGANIC|2.5|Nota privada|1|2
            land-2|La Loma||UNKNOWN|UNKNOWN|||3|4
        """.trimIndent()

        val lands = LandStoreFormat.decode(encoded)

        assertEquals(2, lands.size)
        assertEquals("land-1", lands[0].id)
        assertEquals("Los Olivos", lands[0].name)
        assertEquals(null, lands[0].zone)
        assertEquals("Martos", lands[0].municipality)
        assertEquals(WaterRegime.IRRIGATED, lands[0].waterRegime)
        assertEquals(ProductionMethod.ORGANIC, lands[0].productionMethod)
        assertEquals(LandVariety.UNKNOWN, lands[0].variety)
        assertEquals(null, lands[0].varietyOther)
        assertEquals(2.5, lands[0].areaHectares)
        assertEquals(null, lands[0].treeCount)
        assertEquals("Nota privada", lands[0].notes)
        assertEquals(1L, lands[0].createdAtEpochMillis)
        assertEquals(2L, lands[0].updatedAtEpochMillis)

        assertEquals(null, lands[1].zone)
        assertEquals(null, lands[1].municipality)
        assertEquals(null, lands[1].areaHectares)
        assertEquals(null, lands[1].notes)
    }

    @Test
    fun `a v1 snapshot is rewritten as v2 on the next write`() {
        val v1 = "land-store-v1\nland-1|Los Olivos|Martos|UNKNOWN|UNKNOWN|||1|2"
        var stored: String? = v1
        val storage = object : LandStorage {
            override fun read(): String? = stored

            override fun write(value: String) {
                stored = value
            }
        }
        val repository = LandRepository(storage = storage, idGenerator = { "land-2" })

        val loaded = repository.list().single()
        assertEquals(null, loaded.zone)

        val updated = repository.update(
            id = loaded.id,
            draft = LandDraft(
                name = loaded.name,
                zone = "El Llano",
                municipality = loaded.municipality,
            ),
            now = 5L,
        )

        assertNotNull(updated)
        val written = stored!!
        assertTrue(written.startsWith("land-store-v2\n"))
        val reloaded = LandStoreFormat.decode(written).single()
        assertEquals("El Llano", reloaded.zone)
        assertEquals(LandVariety.UNKNOWN, reloaded.variety)
        assertEquals(null, reloaded.treeCount)
        assertEquals(1L, reloaded.createdAtEpochMillis)
        assertEquals(5L, reloaded.updatedAtEpochMillis)
    }

    @Test
    fun `corrupt records are skipped whole and valid neighbours survive`() {
        val encoded = """
            land-store-v2
            land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
            land-2|Campos rotos|El Llano||DRYLAND|ORGANIC|NO_EXISTE||1.5|85||3|4
            land-3|Línea corta|El Llano||DRYLAND
            land-4|Área mala|La Vega||UNKNOWN|UNKNOWN|UNKNOWN||NaN||5|6
            land-5|Árboles malos|La Vega||UNKNOWN|UNKNOWN|UNKNOWN||1|x|7|8
            land-6|La Loma|La Vega||IRRIGATED|MIXED|OTHER|Royal|2.5|1200|Nota|9|10
        """.trimIndent()

        val lands = LandStoreFormat.decode(encoded)

        assertEquals(listOf("land-1", "land-6"), lands.map { it.id })
        assertEquals("PICUAL", lands[0].variety.name)
        assertEquals(null, lands[0].municipality)
        assertEquals(1.5, lands[0].areaHectares)
        assertEquals(85, lands[0].treeCount)
        assertEquals("Royal", lands[1].varietyOther)
        assertEquals(2.5, lands[1].areaHectares)
        assertEquals(1200, lands[1].treeCount)
        assertEquals("Nota", lands[1].notes)
    }

    @Test
    fun `a v2 header never decodes a v1-shaped line`() {
        val encoded = """
            land-store-v2
            land-1|Los Olivos|Martos|IRRIGATED|ORGANIC|2.5|Nota|1|2
        """.trimIndent()

        assertEquals(emptyList(), LandStoreFormat.decode(encoded))
    }

    @Test
    fun `a v1 header never decodes a v2-shaped line`() {
        val encoded = """
            land-store-v1
            land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
        """.trimIndent()

        assertEquals(emptyList(), LandStoreFormat.decode(encoded))
    }
}
