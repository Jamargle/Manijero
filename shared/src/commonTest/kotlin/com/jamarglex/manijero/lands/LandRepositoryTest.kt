package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class LandRepositoryTest {
    @Test
    fun two_lands_survive_reopening_repository() {
        val storage = MemoryStorage()
        val first = repository(storage).create(LandDraft("Los Olivos", "El Llano"), 1)
        val second = repository(storage).create(
            LandDraft("La Loma", "La Vega", waterRegime = WaterRegime.IRRIGATED),
            2,
        )

        val reopened = repository(storage)
        assertEquals(listOf(first, second), reopened.list())
        assertNotEquals(first.id, second.id)
    }

    @Test
    fun update_and_delete_do_not_change_other_land() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Uno", "El Llano"), 1)
        val second = repository.create(LandDraft("Dos", "La Vega"), 2)

        val updated = repository.update(
            first.id,
            LandDraft("Uno corregido", "El Llano", productionMethod = ProductionMethod.ORGANIC),
            3,
        )
        assertEquals("Uno corregido", updated?.name)
        assertEquals("Dos", repository.list()[1].name)
        assertTrue(repository.delete(first.id))
        assertEquals(listOf(second), repository.list())
        assertNull(repository.update(first.id, LandDraft("No existe", "El Llano"), 4))
    }

    @Test
    fun unknown_values_and_optional_fields_are_preserved() {
        val repository = repository(MemoryStorage())
        val land = repository.create(
            LandDraft(
                name = "  Mi finca  ",
                zone = "  Camino de la Fuente  ",
                municipality = "  Jaén ",
                areaHectares = 2.5,
            ),
            1,
        )
        assertEquals("Mi finca", land.name)
        assertEquals("Camino de la Fuente", land.zone)
        assertEquals("Jaén", land.municipality)
        assertEquals(WaterRegime.UNKNOWN, land.waterRegime)
        assertEquals(LandVariety.UNKNOWN, land.variety)
        assertNull(land.varietyOther)
        assertEquals(2.5, land.areaHectares)
        assertNull(land.treeCount)
    }

    @Test
    fun blank_name_blank_zone_and_invalid_measures_are_rejected() {
        val repository = repository(MemoryStorage())
        assertFailsWith<IllegalArgumentException> { repository.create(LandDraft("  ", "El Llano")) }
        assertFailsWith<IllegalArgumentException> { repository.create(LandDraft("Finca", "   ")) }
        assertFailsWith<IllegalArgumentException> {
            repository.create(LandDraft("Finca", "x".repeat(ZONE_MAX_LENGTH + 1)))
        }
        assertFailsWith<IllegalArgumentException> {
            repository.create(LandDraft("Finca", "El Llano", areaHectares = -1.0))
        }
        assertFailsWith<IllegalArgumentException> {
            repository.create(LandDraft("Finca", "El Llano", treeCount = 0))
        }
    }

    @Test
    fun custom_variety_text_is_required_trimmed_and_cleared_for_the_shortlist() {
        val repository = repository(MemoryStorage())
        assertFailsWith<IllegalArgumentException> {
            repository.create(LandDraft("Finca", "El Llano", variety = LandVariety.OTHER))
        }
        val other = repository.create(
            LandDraft(
                "Finca",
                "El Llano",
                variety = LandVariety.OTHER,
                varietyOther = "  Royal de Cazorla  ",
            ),
            1,
        )
        assertEquals(LandVariety.OTHER, other.variety)
        assertEquals("Royal de Cazorla", other.varietyOther)

        val asPicual = repository.update(
            other.id,
            LandDraft(
                "Finca",
                "El Llano",
                variety = LandVariety.PICUAL,
                varietyOther = "Royal de Cazorla",
            ),
            2,
        )
        assertEquals(LandVariety.PICUAL, asPicual?.variety)
        assertNull(asPicual?.varietyOther, "shortlist variety must not keep stale custom text")
    }

    @Test
    fun areas_are_rounded_to_two_decimals_and_trees_are_kept_exact() {
        val land = repository(MemoryStorage()).create(
            LandDraft("Finca", "El Llano", areaHectares = 1.239, treeCount = 85),
            1,
        )
        assertEquals(1.24, land.areaHectares)
        assertEquals(85, land.treeCount)
    }

    private fun repository(storage: MemoryStorage): LandRepository =
        LandRepository(
            storage = storage,
            idGenerator = object : () -> String {
                private var next = 0

                override fun invoke(): String = "land-${next++}"
            },
        )

    private class MemoryStorage : LandStorage {
        private var value: String? = null

        override fun read(): String? = value

        override fun write(value: String) {
            this.value = value
        }
    }
}
