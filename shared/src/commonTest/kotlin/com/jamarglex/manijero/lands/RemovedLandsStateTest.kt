package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * The pure state of `Terrenos eliminados` and of the second confirmation. A failed read is never an
 * empty list, a re-read never keeps a stale notice, a refusal is never a success, and the confirmation
 * copies only the details the person can already see.
 */
class RemovedLandsStateTest {
    @Test
    fun `a successful read keeps the records and clears the previous result`() {
        val removed = removedLand("land-1", "Los Olivos")

        val state = RemovedLandsState(
            confirmation = RemovedLandsConfirmation.RESTORED,
            failure = RemovedLandsFailure.WRITE_FAILED,
        ).reduce(RemovedLandsAction.LandsLoaded(listOf(removed)))

        assertEquals(listOf(removed), state.lands)
        assertFalse(state.loadFailed)
        assertNull(state.confirmation)
        assertNull(state.failure)
        assertFalse(state.isEmpty)
    }

    @Test
    fun `a failed read is never an empty removed list`() {
        val state = RemovedLandsState(lands = listOf(removedLand("land-1", "Los Olivos")))
            .reduce(RemovedLandsAction.LoadFailed)

        assertTrue(state.loadFailed)
        assertTrue(state.lands.isEmpty())
        assertFalse(state.isEmpty)
    }

    @Test
    fun `a successful empty read is the empty state`() {
        val state = RemovedLandsState().reduce(RemovedLandsAction.LandsLoaded(emptyList()))

        assertTrue(state.isEmpty)
        assertFalse(state.loadFailed)
    }

    @Test
    fun `a reload clears the rows, the failure and the confirmation before the caller reads`() {
        val state = RemovedLandsState(
            lands = listOf(removedLand("land-1", "Los Olivos")),
            confirmation = RemovedLandsConfirmation.DELETED,
            failure = RemovedLandsFailure.LAND_MISSING,
        ).reduce(RemovedLandsAction.ReloadClicked)

        assertEquals(RemovedLandsState(), state)
    }

    @Test
    fun `a restore click clears the previous result so a retry starts clean`() {
        val state = RemovedLandsState(
            lands = listOf(removedLand("land-1", "Los Olivos")),
            confirmation = RemovedLandsConfirmation.DELETED,
            failure = RemovedLandsFailure.WRITE_FAILED,
        ).reduce(RemovedLandsAction.RestoreClicked)

        assertEquals(listOf(removedLand("land-1", "Los Olivos")), state.lands)
        assertNull(state.confirmation)
        assertNull(state.failure)
    }

    @Test
    fun `a refused restore never reads as a success`() {
        val state = RemovedLandsState(lands = listOf(removedLand("land-1", "Los Olivos")))
            .reduce(RemovedLandsAction.RestoreFailed(RemovedLandsFailure.WRITE_FAILED))

        assertEquals(RemovedLandsFailure.WRITE_FAILED, state.failure)
        assertNull(state.confirmation)
        assertEquals(listOf(removedLand("land-1", "Los Olivos")), state.lands)
    }

    @Test
    fun `restore and permanent deletion each confirm their own result`() {
        val restored = RemovedLandsState()
            .reduce(RemovedLandsAction.Restored)
        val deleted = RemovedLandsState()
            .reduce(RemovedLandsAction.Deleted)

        assertEquals(RemovedLandsConfirmation.RESTORED, restored.confirmation)
        assertEquals(RemovedLandsConfirmation.DELETED, deleted.confirmation)
    }

    @Test
    fun `the confirmation copies the stored name and shown details verbatim`() {
        val land = Land(
            id = "land-1",
            name = "La Loma",
            zone = "Linde del arroyo",
            municipality = "Martos",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            variety = LandVariety.OTHER,
            varietyOther = "Royal de Cazorla",
            areaHectares = 2.5,
            treeCount = 85,
            notes = "Nota privada",
            createdAtEpochMillis = 1,
            updatedAtEpochMillis = 2,
        )

        val state = RemovedLand(land, removedAtEpochMillis = 3).toPermanentlyDeleteLandState()

        assertEquals("land-1", state.landId)
        assertEquals("La Loma", state.name)
        assertEquals("Linde del arroyo", state.zone)
        assertEquals("Martos", state.municipality)
        assertEquals(WaterRegime.IRRIGATED, state.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, state.productionMethod)
        assertEquals(LandVariety.OTHER, state.variety)
        assertEquals("Royal de Cazorla", state.varietyOther)
        assertEquals(2.5, state.areaHectares)
        assertEquals(85, state.treeCount)
        assertNull(state.failure, "a fresh confirmation starts without a result")
    }

    @Test
    fun `the permanent deletion confirmation clears a failure on the next attempt`() {
        val state = PermanentlyDeleteLandState(
            landId = "land-1",
            name = "Los Olivos",
            zone = "El Llano",
            municipality = null,
            waterRegime = WaterRegime.UNKNOWN,
            productionMethod = ProductionMethod.UNKNOWN,
            variety = LandVariety.UNKNOWN,
            varietyOther = null,
            areaHectares = null,
            treeCount = null,
        )

        val failed = state.reduce(
            PermanentlyDeleteLandAction.DeleteFailed(PermanentlyDeleteFailure.WRITE_FAILED),
        )
        assertEquals(PermanentlyDeleteFailure.WRITE_FAILED, failed.failure)
        assertEquals("land-1", failed.landId, "the target stays identified for a retry")
        assertNull(failed.reduce(PermanentlyDeleteLandAction.DeleteClicked).failure)
    }

    @Test
    fun `a missing removed record has its own failure`() {
        val state = PermanentlyDeleteLandState(
            landId = "land-1",
            name = "Los Olivos",
            zone = "El Llano",
            municipality = null,
            waterRegime = WaterRegime.UNKNOWN,
            productionMethod = ProductionMethod.UNKNOWN,
            variety = LandVariety.UNKNOWN,
            varietyOther = null,
            areaHectares = null,
            treeCount = null,
        ).reduce(
            PermanentlyDeleteLandAction.DeleteFailed(PermanentlyDeleteFailure.LAND_MISSING),
        )

        assertEquals(PermanentlyDeleteFailure.LAND_MISSING, state.failure)
    }

    private fun removedLand(id: String, name: String): RemovedLand = RemovedLand(
        land = Land(
            id = id,
            name = name,
            zone = "El Llano",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ),
        removedAtEpochMillis = 0,
    )
}
