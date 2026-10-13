package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Integration between the removal confirmation contract and the accepted [LandRepository.delete]
 * semantics: exactly one record leaves the store, every other record — and its encoded line — stays
 * untouched, order is preserved, and an unknown id writes nothing.
 */
class RemoveLandRepositoryTest {
    @Test
    fun removing_one_land_leaves_the_other_record_and_its_encoded_line_untouched() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Los Olivos"), 1)
        val second = repository.create(
            LandDraft(
                name = "La Loma",
                municipality = "Martos",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
                areaHectares = 3.5,
                notes = "Junto al arroyo",
            ),
            2,
        )
        val secondLineBefore = encodedLines(storage.value!!)[1]

        val removed = repository.delete(first.toRemoveLandState().landId)

        assertTrue(removed)
        val lands = repository.list()
        assertEquals(listOf(second.id), lands.map { it.id })
        assertEquals(second, lands[0], "every field of the other land must be unchanged")
        assertEquals(
            secondLineBefore,
            encodedLines(storage.value!!)[0],
            "the surviving land's stored line must be byte-identical",
        )
        assertEquals(1, encodedLines(storage.value!!).size, "no second record may appear")
    }

    @Test
    fun removing_a_middle_land_keeps_the_creation_order_of_the_rest() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Los Olivos"), 1)
        val middle = repository.create(LandDraft("La Loma"), 2)
        val last = repository.create(LandDraft("El Cortijo"), 3)
        val linesBefore = encodedLines(storage.value!!)

        repository.delete(middle.id)

        val lands = repository.list()
        assertEquals(listOf(first, last), lands, "the remaining lands must keep creation order")
        assertEquals(first.id, lands[0].id)
        assertEquals(last.id, lands[1].id)
        assertEquals(linesBefore[0], encodedLines(storage.value!!)[0])
        assertEquals(linesBefore[2], encodedLines(storage.value!!)[1])
    }

    @Test
    fun a_fresh_repository_no_longer_returns_the_removed_land() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val removed = repository.create(LandDraft("Los Olivos"), 1)
        val kept = repository.create(LandDraft("La Loma", "Martos"), 2)

        repository.delete(removed.id)

        val reopened = repository(storage).list()
        assertEquals(listOf(kept), reopened)
        assertFalse(reopened.any { it.id == removed.id })
        assertFalse(reopened.any { it.name == removed.name })
    }

    @Test
    fun deleting_an_unknown_id_returns_false_and_writes_nothing() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        repository.create(LandDraft("Los Olivos"), 1)
        repository.create(LandDraft("La Loma"), 2)
        val before = storage.value

        val removed = repository.delete("land-99")

        assertFalse(removed)
        assertEquals(before, storage.value, "a missing id must not rewrite the snapshot")
        assertEquals(listOf("Los Olivos", "La Loma"), repository.list().map { it.name })
    }

    @Test
    fun removing_the_last_land_leaves_a_valid_empty_store() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val only = repository.create(LandDraft("Los Olivos"), 1)

        val removed = repository.delete(only.id)

        assertTrue(removed)
        assertEquals(emptyList(), repository.list())
        assertNotNullHeaderOnlySnapshot(storage.value!!)
        assertEquals(emptyList(), repository(storage).list(), "a reopened store must read empty")
    }

    private fun assertNotNullHeaderOnlySnapshot(snapshot: String) {
        val lines = snapshot.lineSequence().toList()
        assertEquals("land-store-v1", lines.firstOrNull(), "the store header must survive")
        assertEquals(1, lines.size, "an empty store must be a valid header-only snapshot")
        assertTrue(snapshot.isNotEmpty())
    }

    private fun repository(storage: MemoryStorage) = LandRepository(
        storage = storage,
        idGenerator = object : () -> String {
            private var next = 0
            override fun invoke() = "land-${next++}"
        },
    )

    private fun encodedLines(snapshot: String): List<String> =
        snapshot.lineSequence().drop(1).toList()

    private class MemoryStorage : LandStorage {
        var value: String? = null
        override fun read(): String? = value
        override fun write(value: String) { this.value = value }
    }
}
