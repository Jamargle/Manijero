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

        val state = land.toEditLandState()

        assertEquals("land-7", state.landId)
        assertEquals("La Loma", state.name)
        assertEquals("Linde del arroyo", state.zone)
        assertEquals("Martos", state.municipality)
        assertEquals(WaterRegime.IRRIGATED, state.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, state.productionMethod)
        assertEquals(LandVariety.OTHER, state.variety)
        assertEquals("Royal de Cazorla", state.varietyOther)
        assertEquals("2,5", state.areaText)
        assertEquals("85", state.treeCountText)
        assertEquals("Junto al arroyo", state.preservedNotes)
        assertFalse(state.showNameError)
        assertNull(state.failure)
    }

    @Test
    fun absent_optional_values_become_empty_fields_and_unknown_values_stay_preselected() {
        val state = Land(
            id = "land-1",
            name = "Los Olivos",
            zone = "El Llano",
            municipality = null,
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        assertEquals("El Llano", state.zone)
        assertEquals("", state.municipality)
        assertEquals(WaterRegime.UNKNOWN, state.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, state.productionMethod)
        assertEquals(LandVariety.UNKNOWN, state.variety)
        assertEquals("", state.varietyOther)
        assertEquals("", state.areaText)
        assertEquals("", state.treeCountText)
        assertNull(state.preservedNotes)
        assertFalse(state.showNameError)
        assertNull(state.failure)
    }

    @Test
    fun an_emptied_zone_cannot_be_saved_until_a_zone_is_entered() {
        val base = Land(
            id = "land-1",
            name = "Los Olivos",
            zone = "El Llano",
            municipality = "Martos",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState().copy(zone = "")

        val blocked = base.reduce(EditLandAction.SaveClicked)
        assertTrue(blocked.showZoneError)
        assertEquals(ZoneProblem.BLANK, blocked.zoneIssue)
        assertNull(blocked.toDraftOrNull())

        val corrected = blocked.reduce(EditLandAction.ZoneChanged("El Llano"))
        assertFalse(corrected.showZoneError)
        assertEquals("El Llano", corrected.toDraftOrNull()?.zone)
    }

    @Test
    fun blank_or_whitespace_name_shows_the_error_and_produces_no_draft() {
        val base = Land(
            id = "land-1",
            name = "Los Olivos",
            zone = "El Llano",
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
            zone = "El Llano",
            municipality = "",
            waterRegime = WaterRegime.UNKNOWN,
            productionMethod = ProductionMethod.UNKNOWN,
            variety = LandVariety.UNKNOWN,
            varietyOther = "",
            areaText = "",
            treeCountText = "",
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
            zone = "El Llano",
            municipality = "Martos",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            variety = LandVariety.PICUAL,
            areaHectares = 2.5,
            treeCount = 85,
            notes = "Nota privada",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        val draft = state.reduce(EditLandAction.NameChanged("Los Olivos corregido")).toDraftOrNull()

        assertNotNull(draft)
        assertEquals("Los Olivos corregido", draft.name)
        assertEquals("El Llano", draft.zone)
        assertEquals("Martos", draft.municipality)
        assertEquals(WaterRegime.IRRIGATED, draft.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, draft.productionMethod)
        assertEquals(LandVariety.PICUAL, draft.variety)
        assertEquals(2.5, draft.areaHectares, "an edit must not erase a stored area")
        assertEquals(85, draft.treeCount, "an edit must not erase a stored tree count")
        assertEquals("Nota privada", draft.notes, "an edit must not erase stored notes")
    }

    @Test
    fun clearing_optional_values_drafts_absent_values() {
        val state = Land(
            id = "land-1",
            name = "La Loma",
            zone = "El Llano",
            municipality = "Martos",
            variety = LandVariety.OTHER,
            varietyOther = "Royal de Cazorla",
            areaHectares = 2.5,
            treeCount = 85,
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        val draft = state
            .reduce(EditLandAction.MunicipalityChanged(""))
            .reduce(EditLandAction.VarietySelected(LandVariety.PICUAL))
            .reduce(EditLandAction.AreaChanged(""))
            .reduce(EditLandAction.TreeCountChanged(""))
            .toDraftOrNull()

        assertNotNull(draft)
        assertNull(draft.municipality)
        assertNull(draft.varietyOther)
        assertNull(draft.areaHectares)
        assertNull(draft.treeCount)
    }

    @Test
    fun invalid_measures_block_the_draft_and_keep_the_raw_text() {
        val base = Land(
            id = "land-1",
            name = "La Loma",
            zone = "El Llano",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        val badArea = base.copy(areaText = "mucho").reduce(EditLandAction.SaveClicked)
        assertTrue(badArea.showAreaError)
        assertNull(badArea.toDraftOrNull())
        assertEquals("mucho", badArea.areaText)

        val badTrees = base.copy(treeCountText = "0").reduce(EditLandAction.SaveClicked)
        assertTrue(badTrees.showTreeCountError)
        assertNull(badTrees.toDraftOrNull())
        assertEquals("0", badTrees.treeCountText)

        val corrected = badTrees
            .reduce(EditLandAction.TreeCountChanged("85"))
            .reduce(EditLandAction.SaveClicked)
        assertFalse(corrected.showTreeCountError)
        assertEquals(85, corrected.toDraftOrNull()?.treeCount)
    }

    @Test
    fun a_save_failure_keeps_every_value_and_a_later_edit_clears_it() {
        val base = Land(
            id = "land-1",
            name = "La Loma",
            zone = "El Llano",
            municipality = "Martos",
            waterRegime = WaterRegime.DRYLAND,
            productionMethod = ProductionMethod.ORGANIC,
            variety = LandVariety.ARBEQUINA,
            areaHectares = 1.5,
            treeCount = 85,
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
        assertEquals(LandVariety.ARBEQUINA, failed.variety)
        assertEquals("1,5", failed.areaText)
        assertEquals("85", failed.treeCountText)
        assertEquals("Nota", failed.preservedNotes)
        assertEquals("land-1", failed.landId)
        assertNotNull(failed.toDraftOrNull(), "a failed save must remain retryable")

        val corrected = failed.reduce(EditLandAction.MunicipalityChanged("Úbeda"))
        assertNull(corrected.failure)

        assertNull(failed.reduce(EditLandAction.NameChanged("Otra")).failure)
        assertNull(failed.reduce(EditLandAction.ZoneChanged("La Vega")).failure)
        assertNull(failed.reduce(EditLandAction.WaterRegimeSelected(WaterRegime.MIXED)).failure)
        assertNull(
            failed.reduce(EditLandAction.ProductionMethodSelected(ProductionMethod.MIXED)).failure,
        )
        assertNull(failed.reduce(EditLandAction.VarietySelected(LandVariety.PICUAL)).failure)
        assertNull(failed.reduce(EditLandAction.VarietyOtherChanged("Otra")).failure)
        assertNull(failed.reduce(EditLandAction.AreaChanged("2")).failure)
        assertNull(failed.reduce(EditLandAction.TreeCountChanged("90")).failure)
    }

    @Test
    fun write_failure_and_missing_land_stay_distinguishable() {
        val base = Land(
            id = "land-1",
            name = "Los Olivos",
            zone = "El Llano",
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
    fun field_actions_never_change_the_target_id_or_the_preserved_notes() {
        val base = Land(
            id = "land-42",
            name = "Los Olivos",
            zone = "El Llano",
            municipality = "Martos",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            variety = LandVariety.PICUAL,
            areaHectares = 4.25,
            treeCount = 120,
            notes = "Linde norte",
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ).toEditLandState()

        val actions = listOf(
            EditLandAction.NameChanged("Otro nombre"),
            EditLandAction.ZoneChanged("La Vega"),
            EditLandAction.MunicipalityChanged("Úbeda"),
            EditLandAction.WaterRegimeSelected(WaterRegime.DRYLAND),
            EditLandAction.ProductionMethodSelected(ProductionMethod.CONVENTIONAL),
            EditLandAction.VarietySelected(LandVariety.MIXED),
            EditLandAction.VarietyOtherChanged("Otra"),
            EditLandAction.AreaChanged("2"),
            EditLandAction.TreeCountChanged("90"),
            EditLandAction.SaveClicked,
            EditLandAction.SaveFailed(EditLandFailure.LAND_MISSING),
        )

        actions.forEach { action ->
            val reduced = base.reduce(action)
            assertEquals("land-42", reduced.landId, "$action must not retarget the edit")
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
            val state = Land(
                id = "land-1",
                name = typed,
                zone = "  Cañada de la Encina  ",
                createdAtEpochMillis = 0,
                updatedAtEpochMillis = 0,
            ).toEditLandState()

            assertEquals(typed, state.name, "raw text must survive for correction")
            assertEquals(name, state.toDraftOrNull()?.name)
            assertEquals("Cañada de la Encina", state.toDraftOrNull()?.zone)
        }
    }
}
