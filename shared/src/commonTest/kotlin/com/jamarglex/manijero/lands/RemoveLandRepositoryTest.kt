package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Integration between the removal confirmation contract and the accepted lifecycle semantics: exactly
 * one record leaves the active list and enters the removed list, every other record — and its encoded
 * line — stays untouched, order is preserved, and an unknown id writes nothing.
 */
class RemoveLandRepositoryTest {
    @Test
    fun removing_one_land_leaves_the_other_record_and_its_encoded_line_untouched() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        val second = repository.create(
            LandDraft(
                name = "La Loma",
                zone = "Linde del arroyo",
                municipality = "Martos",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
                areaHectares = 3.5,
                notes = "Junto al arroyo",
            ),
            2,
        )
        val secondLineBefore = activeLines(storage.value!!)[1]

        val removed = repository.moveToRemoved(first.toRemoveLandState().landId, now = 9)

        assertEquals(LandLifecycleResult.Done(first), removed)
        val lands = repository.list()
        assertEquals(listOf(second.id), lands.map { it.id })
        assertEquals(second, lands[0], "every field of the other land must be unchanged")
        assertEquals(
            secondLineBefore,
            activeLines(storage.value!!)[0],
            "the surviving land's stored line must be byte-identical",
        )
        assertEquals(1, activeLines(storage.value!!).size, "no second active record may appear")
        assertEquals(listOf(RemovedLand(first, 9)), repository.listRemoved())
    }

    @Test
    fun removing_a_middle_land_keeps_the_creation_order_of_the_rest() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        val middle = repository.create(LandDraft("La Loma", "La Vega"), 2)
        val last = repository.create(LandDraft("El Cortijo", "Las Eras"), 3)
        val linesBefore = activeLines(storage.value!!)

        repository.moveToRemoved(middle.id)

        val lands = repository.list()
        assertEquals(listOf(first, last), lands, "the remaining lands must keep creation order")
        assertEquals(first.id, lands[0].id)
        assertEquals(last.id, lands[1].id)
        assertEquals(linesBefore[0], activeLines(storage.value!!)[0])
        assertEquals(linesBefore[2], activeLines(storage.value!!)[1])
    }

    @Test
    fun a_fresh_repository_no_longer_returns_the_removed_land_as_active() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val removed = repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        val kept = repository.create(LandDraft("La Loma", "La Vega", municipality = "Martos"), 2)

        repository.moveToRemoved(removed.id, now = 7)

        val reopened = repository(storage)
        assertEquals(listOf(kept), reopened.list())
        assertFalse(reopened.list().any { it.id == removed.id })
        assertFalse(reopened.list().any { it.name == removed.name })
        assertEquals(listOf(RemovedLand(removed, 7)), reopened.listRemoved())
    }

    @Test
    fun removing_an_unknown_id_returns_missing_and_writes_nothing() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        repository.create(LandDraft("La Loma", "La Vega"), 2)
        val before = storage.value

        val removed = repository.moveToRemoved("land-99")

        assertEquals(LandLifecycleResult.Missing, removed)
        assertEquals(before, storage.value, "a missing id must not rewrite the snapshot")
        assertEquals(listOf("Los Olivos", "La Loma"), repository.list().map { it.name })
        assertEquals(emptyList(), repository.listRemoved())
    }

    @Test
    fun removing_the_last_land_leaves_a_valid_empty_active_list() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val only = repository.create(LandDraft("Los Olivos", "El Llano"), 1)

        val removed = repository.moveToRemoved(only.id, now = 3)

        assertEquals(LandLifecycleResult.Done(only), removed)
        assertEquals(emptyList(), repository.list())
        assertValidEmptyActiveSnapshot(storage.value!!)
        assertEquals(listOf(RemovedLand(only, 3)), repository(storage).listRemoved())
    }

    /**
     * An empty active list is a complete aggregate with both section markers, not a header-only file:
     * the removed section still holds the record that left `Mis terrenos`.
     */
    private fun assertValidEmptyActiveSnapshot(snapshot: String) {
        val lines = snapshot.lineSequence().toList()
        assertEquals("land-store-v2", lines.firstOrNull(), "the store header must survive")
        assertEquals("active", lines.getOrNull(1), "the active section marker must survive")
        assertEquals("removed", lines.getOrNull(2), "the removed section marker must survive")
        assertEquals(emptyList(), activeLines(snapshot), "no active record may remain")
        assertEquals(
            1,
            lines.subList(3, lines.size).size,
            "the removed record must be kept after the removed marker",
        )
        assertTrue(snapshot.isNotEmpty())
    }

    private fun repository(storage: MemoryStorage): LandRepository =
        LandRepository(
            storage = storage,
            idGenerator = object : () -> String {
                private var next = 0

                override fun invoke(): String = "land-${next++}"
            },
        )

    /** The record lines of the `active` section only; the section markers are not records. */
    private fun activeLines(snapshot: String): List<String> {
        val lines = snapshot.lineSequence().toList()
        val start = lines.indexOf("active")
        val end = lines.indexOf("removed")
        return lines.subList(start + 1, end)
    }

    private class MemoryStorage : LandStorage {
        var value: String? = null

        override fun read(): String? = value

        override fun write(value: String) {
            this.value = value
        }
    }
}
