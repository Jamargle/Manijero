package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Pure form contract for the "Editar terreno" flow. Every test starts from a directly constructed
 * [Land] so no storage, resource, or Compose type is involved.
 */
class EditLandStateTest {
    @Test
    fun prefilled_state_mirrors_the_stored_record() {
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

        val state = land.toEditLandState()

        assertEquals("land-7", state.landId)
        assertEquals("La Loma", state.name)
        assertEquals("Martos", state.municipality)
        assertEquals(WaterRegime.IRRIGATED, state.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, state.productionMethod)
        assertEquals(2.5, state.preservedAreaHectares)
        assertEquals("Junto al arroyo", state.preservedNotes)
        assertFalse(state.showNameError)
        assertNull(state.failure)
    }

    @Test
    fun absent_municipality_becomes_an_empty_field_and_unknown_values_stay_preselected() {
        val state = Land(
            id = "land-1",
            name = "Los Olivos",
            municipality = null,
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        assertEquals("", state.municipality)
        assertEquals(WaterRegime.UNKNOWN, state.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, state.productionMethod)
        assertNull(state.preservedAreaHectares)
        assertNull(state.preservedNotes)
        assertFalse(state.showNameError)
        assertNull(state.failure)
    }

    @Test
    fun blank_or_whitespace_name_shows_the_error_and_produces_no_draft() {
        val base = Land(
            id = "land-1",
            name = "Los Olivos",
            municipality = "Martos",
            waterRegime = WaterRegime.IRRIGATED,
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        for (blank in listOf("", "   ", "\t\n")) {
            val state = base.copy(name = blank).reduce(EditLandAction.SaveClicked)

            assertFalse(state.hasName)
            assertTrue(state.showNameError, "expected a required-name error for <$blank>")
            assertNull(state.toDraftOrNull(), "no record may be built for <$blank>")
            assertEquals("Martos", state.municipality, "other edited values must stay available")
            assertEquals(WaterRegime.IRRIGATED, state.waterRegime)
        }
    }

    @Test
    fun correcting_a_blank_name_clears_the_required_error() {
        val errored = EditLandState(
            landId = "land-1",
            name = "   ",
            municipality = "",
            waterRegime = WaterRegime.UNKNOWN,
            productionMethod = ProductionMethod.UNKNOWN,
            preservedAreaHectares = null,
            preservedNotes = null,
        ).reduce(EditLandAction.SaveClicked)
        assertTrue(errored.showNameError)

        val corrected = errored.reduce(EditLandAction.NameChanged("Los Olivos"))

        assertFalse(corrected.showNameError)
        assertNotNull(corrected.toDraftOrNull())
    }

    @Test
    fun a_name_only_correction_carries_the_untouched_values_into_the_draft() {
        val state = Land(
            id = "land-1",
            name = "Los Olivos",
            municipality = "Martos",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            areaHectares = 2.5,
            notes = "Nota privada",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        val draft = state.reduce(EditLandAction.NameChanged("Los Olivos corregido")).toDraftOrNull()

        assertNotNull(draft)
        assertEquals("Los Olivos corregido", draft.name)
        assertEquals("Martos", draft.municipality)
        assertEquals(WaterRegime.IRRIGATED, draft.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, draft.productionMethod)
        assertEquals(2.5, draft.areaHectares, "an edit must not erase a stored area")
        assertEquals("Nota privada", draft.notes, "an edit must not erase stored notes")
    }

    @Test
    fun clearing_the_municipality_drafts_an_absent_value() {
        val state = Land(
            id = "land-1",
            name = "La Loma",
            municipality = "Martos",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        assertNull(
            state.reduce(EditLandAction.MunicipalityChanged("")).toDraftOrNull()?.municipality,
        )
        assertNull(
            state.reduce(EditLandAction.MunicipalityChanged("   ")).toDraftOrNull()?.municipality,
        )
        assertEquals(
            "Úbeda",
            state.reduce(EditLandAction.MunicipalityChanged("  Úbeda ")).toDraftOrNull()?.municipality,
        )
    }

    @Test
    fun selecting_unknown_after_a_known_value_drafts_unknown() {
        val state = Land(
            id = "land-1",
            name = "La Loma",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        val draft = state
            .reduce(EditLandAction.WaterRegimeSelected(WaterRegime.UNKNOWN))
            .reduce(EditLandAction.ProductionMethodSelected(ProductionMethod.UNKNOWN))
            .toDraftOrNull()

        assertNotNull(draft)
        assertEquals(WaterRegime.UNKNOWN, draft.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, draft.productionMethod)
    }

    @Test
    fun a_deliberate_mixed_value_survives_the_draft() {
        val state = Land(
            id = "land-1",
            name = "Los Olivos",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        val draft = state
            .reduce(EditLandAction.WaterRegimeSelected(WaterRegime.MIXED))
            .reduce(EditLandAction.ProductionMethodSelected(ProductionMethod.MIXED))
            .toDraftOrNull()

        assertNotNull(draft)
        assertEquals(WaterRegime.MIXED, draft.waterRegime)
        assertEquals(ProductionMethod.MIXED, draft.productionMethod)
    }

    @Test
    fun a_save_failure_keeps_every_value_and_a_later_edit_clears_it() {
        val base = Land(
            id = "land-1",
            name = "La Loma",
            municipality = "Martos",
            waterRegime = WaterRegime.DRYLAND,
            productionMethod = ProductionMethod.ORGANIC,
            areaHectares = 1.5,
            notes = "Nota",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()
            .reduce(EditLandAction.NameChanged("La Loma corregida"))
            .reduce(EditLandAction.MunicipalityChanged("Jaén"))

        val failed = base.reduce(EditLandAction.SaveFailed(EditLandFailure.WRITE_FAILED))

        assertEquals(EditLandFailure.WRITE_FAILED, failed.failure)
        assertEquals("La Loma corregida", failed.name)
        assertEquals("Jaén", failed.municipality)
        assertEquals(WaterRegime.DRYLAND, failed.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, failed.productionMethod)
        assertEquals(1.5, failed.preservedAreaHectares)
        assertEquals("Nota", failed.preservedNotes)
        assertEquals("land-1", failed.landId)
        assertNotNull(failed.toDraftOrNull(), "a failed save must remain retryable")

        val corrected = failed.reduce(EditLandAction.MunicipalityChanged("Úbeda"))
        assertNull(corrected.failure)

        assertNull(failed.reduce(EditLandAction.NameChanged("Otra")).failure)
        assertNull(failed.reduce(EditLandAction.WaterRegimeSelected(WaterRegime.MIXED)).failure)
        assertNull(
            failed.reduce(EditLandAction.ProductionMethodSelected(ProductionMethod.MIXED)).failure,
        )
    }

    @Test
    fun write_failure_and_missing_land_stay_distinguishable() {
        val base = Land(
            id = "land-1",
            name = "Los Olivos",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        val writeFailed = base.reduce(EditLandAction.SaveFailed(EditLandFailure.WRITE_FAILED))
        val missing = base.reduce(EditLandAction.SaveFailed(EditLandFailure.LAND_MISSING))

        assertEquals(EditLandFailure.WRITE_FAILED, writeFailed.failure)
        assertEquals(EditLandFailure.LAND_MISSING, missing.failure)
        assertFalse(writeFailed.failure == missing.failure)
        assertEquals(base.name, missing.name)
        assertEquals(base.landId, missing.landId)
        assertFalse(missing.showNameError)
    }

    @Test
    fun field_actions_never_change_the_target_id_or_the_preserved_attributes() {
        val base = Land(
            id = "land-42",
            name = "Los Olivos",
            municipality = "Martos",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            areaHectares = 4.25,
            notes = "Linde norte",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        val actions = listOf(
            EditLandAction.NameChanged("Otro nombre"),
            EditLandAction.MunicipalityChanged("Úbeda"),
            EditLandAction.WaterRegimeSelected(WaterRegime.DRYLAND),
            EditLandAction.ProductionMethodSelected(ProductionMethod.CONVENTIONAL),
            EditLandAction.SaveClicked,
            EditLandAction.SaveFailed(EditLandFailure.LAND_MISSING),
        )

        actions.forEach { action ->
            val reduced = base.reduce(action)
            assertEquals("land-42", reduced.landId, "$action must not retarget the edit")
            assertEquals(4.25, reduced.preservedAreaHectares, "$action must not drop the area")
            assertEquals("Linde norte", reduced.preservedNotes, "$action must not drop the notes")
        }
    }

    @Test
    fun unicode_emoji_and_long_names_survive_verbatim_while_the_draft_is_trimmed() {
        val names = listOf(
            "Olivar 😀 de la Peña",
            "El olivar de mi abuelo junto al camino de la fuente",
            "El olivar de mi abuelo junto al camino de la fuente".repeat(20),
        )

        names.forEach { name ->
            val typed = "  $name  "
            val state = EditLandState(
                landId = "land-1",
                name = typed,
                municipality = "",
                waterRegime = WaterRegime.UNKNOWN,
                productionMethod = ProductionMethod.UNKNOWN,
                preservedAreaHectares = null,
                preservedNotes = null,
            )

            assertEquals(typed, state.name, "raw text must survive for correction")
            assertEquals(name, state.toDraftOrNull()?.name)
        }
    }
}
