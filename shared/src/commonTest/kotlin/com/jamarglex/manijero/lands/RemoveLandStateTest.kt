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
            zone = "Linde del arroyo",
            municipality = "Martos",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            variety = LandVariety.OTHER,
            varietyOther = "Royal de Cazorla",
            areaHectares = 2.5,
            treeCount = 85,
            notes = "Junto al arroyo",
            createdAtEpochMillis = 1,
            updatedAtEpochMillis = 2,
        )

        val state = land.toRemoveLandState()

        assertEquals("land-7", state.landId)
        assertEquals("La Loma", state.name)
        assertEquals("Linde del arroyo", state.zone)
        assertEquals("Martos", state.municipality)
        assertEquals(WaterRegime.IRRIGATED, state.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, state.productionMethod)
        assertEquals(LandVariety.OTHER, state.variety)
        assertEquals("Royal de Cazorla", state.varietyOther)
        assertEquals(2.5, state.areaHectares)
        assertEquals(85, state.treeCount)
        assertNull(state.failure)
    }

    @Test
    fun a_name_only_land_keeps_its_zone_and_absent_optional_values() {
        val state = Land(
            id = "land-1",
            name = "Los Olivos",
            zone = "El Llano",
            municipality = null,
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toRemoveLandState()

        assertEquals("El Llano", state.zone)
        assertNull(state.municipality)
        assertEquals(LandVariety.UNKNOWN, state.variety)
        assertNull(state.varietyOther)
        assertNull(state.areaHectares)
        assertEquals(WaterRegime.UNKNOWN, state.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, state.productionMethod)
        assertNull(state.failure)
    }

    @Test
    fun remove_clicked_clears_a_previous_failure_and_changes_nothing_else() {
        val base = removeState(failure = RemoveLandFailure.WRITE_FAILED)

        val cleared = base.reduce(RemoveLandAction.RemoveClicked)

        assertNull(cleared.failure, "a retry must start clean")
        assertEquals(base.copy(failure = null), cleared)
    }

    @Test
    fun a_remove_failure_keeps_every_field_and_stays_retryable() {
        val base = removeState()

        val failed = base.reduce(RemoveLandAction.RemoveFailed(RemoveLandFailure.WRITE_FAILED))

        assertEquals(RemoveLandFailure.WRITE_FAILED, failed.failure)
        assertEquals(base, failed.copy(failure = null))
        assertEquals(base.zone, failed.zone)
        assertEquals(base.variety, failed.variety)
        assertEquals(base.areaHectares, failed.areaHectares)
        assertEquals(base.treeCount, failed.treeCount)

        val retried = failed.reduce(RemoveLandAction.RemoveClicked)
        assertNull(retried.failure)
        assertEquals(base.landId, retried.landId, "the retry must still target the same land")
        assertEquals(base.name, retried.name)
    }

    @Test
    fun write_failure_and_missing_land_stay_distinguishable() {
        val base = removeState()

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
        val base = removeState()

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
                zone = "El Llano",
                createdAtEpochMillis = 0,
                updatedAtEpochMillis = 0,
            ).toRemoveLandState()

            assertEquals(name, state.name)
        }
    }

    @Test
    fun the_confirmation_carries_only_the_fields_the_shared_details_show() {
        val land = Land(
            id = "land-secreto",
            name = "Los Olivos",
            zone = "El Llano",
            areaHectares = 12.75,
            treeCount = 1200,
            notes = "Nota privada",
            createdAtEpochMillis = 5,
            updatedAtEpochMillis = 6,
        )

        val state = land.toRemoveLandState()

        // Data-class equality proves nothing else (no notes or timestamp) is carried.
        assertEquals(
            RemoveLandState(
                landId = "land-secreto",
                name = "Los Olivos",
                zone = "El Llano",
                municipality = null,
                waterRegime = WaterRegime.UNKNOWN,
                productionMethod = ProductionMethod.UNKNOWN,
                variety = LandVariety.UNKNOWN,
                varietyOther = null,
                areaHectares = 12.75,
                treeCount = 1200,
            ),
            state,
        )
    }

    private fun removeState(
        failure: RemoveLandFailure? = null,
    ) = RemoveLandState(
        landId = "land-42",
        name = "Los Olivos",
        zone = "El Llano",
        municipality = "Martos",
        waterRegime = WaterRegime.DRYLAND,
        productionMethod = ProductionMethod.ORGANIC,
        variety = LandVariety.PICUAL,
        varietyOther = null,
        areaHectares = 2.5,
        treeCount = 85,
        failure = failure,
    )
}
