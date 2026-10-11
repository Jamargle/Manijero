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
        val first = repository(storage).create(LandDraft("Los Olivos"), 1)
        val second = repository(storage).create(
            LandDraft("La Loma", waterRegime = WaterRegime.IRRIGATED), 2,
        )

        val reopened = repository(storage)
        assertEquals(listOf(first, second), reopened.list())
        assertNotEquals(first.id, second.id)
    }

    @Test
    fun update_and_delete_do_not_change_other_land() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Uno"), 1)
        val second = repository.create(LandDraft("Dos"), 2)

        val updated = repository.update(
            first.id,
            LandDraft("Uno corregido", productionMethod = ProductionMethod.ORGANIC),
            3,
        )
        assertEquals("Uno corregido", updated?.name)
        assertEquals("Dos", repository.list()[1].name)
        assertTrue(repository.delete(first.id))
        assertEquals(listOf(second), repository.list())
        assertNull(repository.update(first.id, LandDraft("No existe"), 4))
    }

    @Test
    fun unknown_values_and_optional_fields_are_preserved() {
        val repository = repository(MemoryStorage())
        val land = repository.create(
            LandDraft("  Mi finca  ", municipality = "  Jaén ", areaHectares = 2.5), 1,
        )
        assertEquals("Mi finca", land.name)
        assertEquals("Jaén", land.municipality)
        assertEquals(WaterRegime.UNKNOWN, land.waterRegime)
        assertEquals(2.5, land.areaHectares)
    }

    @Test
    fun blank_or_negative_input_is_rejected() {
        val repository = repository(MemoryStorage())
        assertFailsWith<IllegalArgumentException> { repository.create(LandDraft("  ")) }
        assertFailsWith<IllegalArgumentException> {
            repository.create(LandDraft("Finca", areaHectares = -1.0))
        }
    }

    private fun repository(storage: MemoryStorage) = LandRepository(
        storage = storage,
        idGenerator = object : () -> String {
            private var next = 0
            override fun invoke() = "land-${next++}"
        },
    )

    private class MemoryStorage : LandStorage {
        var value: String? = null
        override fun read(): String? = value
        override fun write(value: String) { this.value = value }
    }
}
