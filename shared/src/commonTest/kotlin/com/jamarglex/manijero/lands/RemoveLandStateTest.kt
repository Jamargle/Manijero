package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull

/**
 * Pure confirmation contract for the "Eliminar terreno" flow. Every test starts from a directly
 * constructed [Land] so no storage, resource, or Compose type is involved.
 */
class RemoveLandStateTest {
    @Test
    fun confirmation_target_copies_the_identity_fields_it_shows() {
        val land = Land(
            id = "land-7",
            name = "La Loma",
            municipality = "Martos",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            areaHectares = 2.5,
            notes = "Junto al arroyo",
            createdAtEpochMillis = 1,
            updatedAtEpochMillis = 2,
        )

        val state = land.toRemoveLandState()

        assertEquals("land-7", state.landId)
        assertEquals("La Loma", state.name)
        assertEquals("Martos", state.municipality)
        assertEquals(WaterRegime.IRRIGATED, state.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, state.productionMethod)
        assertNull(state.failure)
    }

    @Test
    fun a_name_only_land_keeps_an_absent_municipality_and_unknown_attributes() {
        val state = Land(
            id = "land-1",
            name = "Los Olivos",
            municipality = null,
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toRemoveLandState()

        assertNull(state.municipality)
        assertEquals(WaterRegime.UNKNOWN, state.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, state.productionMethod)
        assertNull(state.failure)
    }

    @Test
    fun remove_clicked_clears_a_previous_failure_and_changes_nothing_else() {
        val base = RemoveLandState(
            landId = "land-42",
            name = "Los Olivos",
            municipality = "Martos",
            waterRegime = WaterRegime.DRYLAND,
            productionMethod = ProductionMethod.ORGANIC,
            failure = RemoveLandFailure.WRITE_FAILED,
        )

        val cleared = base.reduce(RemoveLandAction.RemoveClicked)

        assertNull(cleared.failure, "a retry must start clean")
        assertEquals(base.landId, cleared.landId)
        assertEquals(base.name, cleared.name)
        assertEquals(base.municipality, cleared.municipality)
        assertEquals(base.waterRegime, cleared.waterRegime)
        assertEquals(base.productionMethod, cleared.productionMethod)
    }

    @Test
    fun a_remove_failure_keeps_every_field_and_stays_retryable() {
        val base = RemoveLandState(
            landId = "land-1",
            name = "La Loma",
            municipality = "Jaén",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.MIXED,
        )

        val failed = base.reduce(RemoveLandAction.RemoveFailed(RemoveLandFailure.WRITE_FAILED))

        assertEquals(RemoveLandFailure.WRITE_FAILED, failed.failure)
        assertEquals("land-1", failed.landId)
        assertEquals("La Loma", failed.name)
        assertEquals("Jaén", failed.municipality)
        assertEquals(WaterRegime.IRRIGATED, failed.waterRegime)
        assertEquals(ProductionMethod.MIXED, failed.productionMethod)

        val retried = failed.reduce(RemoveLandAction.RemoveClicked)
        assertNull(retried.failure)
        assertEquals("land-1", retried.landId, "the retry must still target the same land")
        assertEquals("La Loma", retried.name)
    }

    @Test
    fun write_failure_and_missing_land_stay_distinguishable() {
        val base = RemoveLandState(
            landId = "land-1",
            name = "Los Olivos",
            municipality = null,
            waterRegime = WaterRegime.UNKNOWN,
            productionMethod = ProductionMethod.UNKNOWN,
        )

        val writeFailed = base.reduce(RemoveLandAction.RemoveFailed(RemoveLandFailure.WRITE_FAILED))
        val missing = base.reduce(RemoveLandAction.RemoveFailed(RemoveLandFailure.LAND_MISSING))

        assertEquals(RemoveLandFailure.WRITE_FAILED, writeFailed.failure)
        assertEquals(RemoveLandFailure.LAND_MISSING, missing.failure)
        assertFalse(writeFailed.failure == missing.failure)
        assertEquals(base.landId, missing.landId)
        assertEquals(base.name, missing.name)
    }

    @Test
    fun actions_never_retarget_the_record_being_removed() {
        val base = RemoveLandState(
            landId = "land-42",
            name = "Los Olivos",
            municipality = "Martos",
            waterRegime = WaterRegime.DRYLAND,
            productionMethod = ProductionMethod.CONVENTIONAL,
        )

        val actions = listOf(
            RemoveLandAction.RemoveClicked,
            RemoveLandAction.RemoveFailed(RemoveLandFailure.WRITE_FAILED),
            RemoveLandAction.RemoveFailed(RemoveLandFailure.LAND_MISSING),
        )

        actions.forEach { action ->
            val reduced = base.reduce(action)
            assertEquals("land-42", reduced.landId, "$action must not retarget the removal")
            assertEquals("Los Olivos", reduced.name)
        }
    }

    @Test
    fun unicode_emoji_and_long_names_survive_verbatim() {
        val names = listOf(
            "Olivar 😀 de la Peña",
            "El olivar de mi abuelo junto al camino de la fuente",
            "El olivar de mi abuelo junto al camino de la fuente".repeat(20),
        )

        names.forEach { name ->
            val state = Land(
                id = "land-1",
                name = name,
                createdAtEpochMillis = 0,
                updatedAtEpochMillis = 0,
            ).toRemoveLandState()

            assertEquals(name, state.name)
        }
    }

    @Test
    fun the_confirmation_carries_only_the_identity_fields() {
        val land = Land(
            id = "land-secreto",
            name = "Los Olivos",
            areaHectares = 12.75,
            notes = "Nota privada",
            createdAtEpochMillis = 5,
            updatedAtEpochMillis = 6,
        )

        val state = land.toRemoveLandState()

        // Data-class equality proves nothing else (no area, notes, or timestamp) is carried.
        assertEquals(
            RemoveLandState(
                landId = "land-secreto",
                name = "Los Olivos",
                municipality = null,
                waterRegime = WaterRegime.UNKNOWN,
                productionMethod = ProductionMethod.UNKNOWN,
            ),
            state,
        )
    }
}
