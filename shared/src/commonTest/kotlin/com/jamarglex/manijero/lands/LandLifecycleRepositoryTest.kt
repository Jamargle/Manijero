package com.jamarglex.manijero.lands

import com.jamarglex.manijero.chat.landContextFor
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * The recoverable lifecycle contract: moving a land out of `Mis terrenos`, restoring it, and deleting
 * it for good. Every transition writes one complete aggregate, preserves record data and the order of
 * the records it does not touch, and reports missing records and refused writes distinctly.
 */
class LandLifecycleRepositoryTest {
    @Test
    fun moving_a_land_preserves_every_field_and_the_order_of_the_rest() {
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
                variety = LandVariety.OTHER,
                varietyOther = "Royal de Cazorla",
                areaHectares = 3.5,
                treeCount = 120,
                notes = "Junto al arroyo",
            ),
            2,
        )
        val third = repository.create(LandDraft("El Cortijo", "Las Eras"), 3)

        val result = repository.moveToRemoved(second.id, now = 99)

        assertEquals(LandLifecycleResult.Done(second), result)
        assertEquals(listOf(first, third), repository.list(), "the other lands keep their order")
        assertEquals(listOf(RemovedLand(second, 99)), repository.listRemoved())
    }

    @Test
    fun restore_returns_exactly_that_record_to_the_end_of_the_active_list() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        val second = repository.create(LandDraft("La Loma", "La Vega"), 2)
        val third = repository.create(LandDraft("El Cortijo", "Las Eras"), 3)
        repository.moveToRemoved(second.id, now = 10)

        val result = repository.restore(second.id)

        assertEquals(LandLifecycleResult.Done(second), result)
        assertEquals(
            listOf(first, third, second),
            repository.list(),
            "the restored land returns to the end and no other land moves",
        )
        assertEquals(emptyList(), repository.listRemoved())
        assertEquals(
            listOf(first, third, second),
            repository(storage).list(),
            "the restored position must survive a restart",
        )
    }

    @Test
    fun restore_of_a_missing_removed_id_reports_missing_and_writes_nothing() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val land = repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        val before = storage.value

        assertEquals(LandLifecycleResult.Missing, repository.restore(land.id))
        assertEquals(LandLifecycleResult.Missing, repository.restore("land-99"))

        assertEquals(before, storage.value, "an active or unknown id is not a restore target")
        assertEquals(listOf(land), repository.list())
        assertEquals(emptyList(), repository.listRemoved())
    }

    @Test
    fun permanent_deletion_removes_only_the_named_removed_record() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val keptActive = repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        val removedFirst = repository.create(LandDraft("La Loma", "La Vega"), 2)
        val removedSecond = repository.create(LandDraft("El Cortijo", "Las Eras"), 3)
        repository.moveToRemoved(removedFirst.id, now = 4)
        repository.moveToRemoved(removedSecond.id, now = 5)

        val result = repository.permanentlyDelete(removedFirst.id)

        assertEquals(LandLifecycleResult.Done(removedFirst), result)
        assertEquals(listOf(keptActive), repository.list())
        assertEquals(listOf(RemovedLand(removedSecond, 5)), repository.listRemoved())

        val reopened = repository(storage)
        assertEquals(listOf(keptActive), reopened.list())
        assertEquals(listOf(removedSecond.id), reopened.listRemoved().map { it.land.id })
    }

    @Test
    fun an_active_id_is_not_a_permanent_deletion_target() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val land = repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        val before = storage.value

        assertEquals(LandLifecycleResult.Missing, repository.permanentlyDelete(land.id))

        assertEquals(before, storage.value, "permanent deletion must not touch the active list")
        assertEquals(listOf(land), repository.list())
    }

    @Test
    fun duplicate_names_are_told_apart_by_their_ids() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        val second = repository.create(LandDraft("Los Olivos", "Las Eras"), 2)

        repository.moveToRemoved(second.id, now = 3)

        assertEquals(listOf(first), repository.list(), "only the named duplicate must move")
        assertEquals(listOf(second), repository.listRemoved().map { it.land })
    }

    @Test
    fun a_refused_write_reports_storage_failure_and_keeps_the_store() {
        val storage = FailingWriteStorage()
        val repository = repository(storage)
        val land = repository.create(LandDraft("Los Olivos", "El Llano"), 1)

        storage.refuseWrites = true
        val activeSnapshot = storage.value
        assertEquals(LandLifecycleResult.StorageFailed, repository.moveToRemoved(land.id))
        assertEquals(activeSnapshot, storage.value, "a refused move must leave the aggregate untouched")

        storage.refuseWrites = false
        assertEquals(LandLifecycleResult.Done(land), repository.moveToRemoved(land.id, now = 5))
        val removedSnapshot = storage.value
        storage.refuseWrites = true
        assertEquals(LandLifecycleResult.StorageFailed, repository.restore(land.id))
        assertEquals(removedSnapshot, storage.value, "a refused restore must write nothing")
        assertEquals(LandLifecycleResult.StorageFailed, repository.permanentlyDelete(land.id))
        assertEquals(removedSnapshot, storage.value, "a refused deletion must write nothing")

        storage.refuseWrites = false
        assertEquals(LandLifecycleResult.Done(land), repository.restore(land.id))
        val restoredSnapshot = storage.value
        storage.refuseWrites = true
        assertEquals(LandLifecycleResult.StorageFailed, repository.moveToRemoved(land.id))
        assertEquals(restoredSnapshot, storage.value)
    }

    @Test
    fun removed_lands_never_reach_the_active_list_or_a_question_context() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val active = repository.create(
            LandDraft(
                name = "Los Olivos",
                zone = "El Llano",
                waterRegime = WaterRegime.DRYLAND,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            1,
        )
        val removed = repository.create(
            LandDraft(
                name = "La Loma",
                zone = "La Vega",
                municipality = "Martos",
                waterRegime = WaterRegime.IRRIGATED,
            ),
            2,
        )
        repository.moveToRemoved(removed.id, now = 3)

        val activeLands = repository.list()
        assertEquals(listOf(active), activeLands)
        assertFalse(activeLands.any { it.id == removed.id })
        val context = landContextFor("¿Qué riego necesita?", activeLands)
        assertEquals(listOf(active.id), context.lands.map { it.id })
        assertTrue(context.lands.none { it.id == removed.id })
    }

    private fun repository(storage: LandStorage): LandRepository = LandRepository(
        storage = storage,
        idGenerator = object : () -> String {
            private var next = 0

            override fun invoke(): String = "land-${next++}"
        },
    )

    private class MemoryStorage : LandStorage {
        var value: String? = null

        override fun read(): String? = value

        override fun write(value: String) {
            this.value = value
        }
    }

    private class FailingWriteStorage : LandStorage {
        var value: String? = null
        var refuseWrites: Boolean = false

        override fun read(): String? = value

        override fun write(value: String) {
            if (refuseWrites) error("storage refused the write")
            this.value = value
        }
    }
}
