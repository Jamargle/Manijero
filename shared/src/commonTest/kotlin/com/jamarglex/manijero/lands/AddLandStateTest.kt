package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class AddLandStateTest {
    @Test
    fun `default form offers unknown for variety water and production`() {
        val state = AddLandState()

        assertEquals(WaterRegime.UNKNOWN, state.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, state.productionMethod)
        assertEquals(LandVariety.UNKNOWN, state.variety)
        assertFalse(state.showNameError)
        assertFalse(state.showZoneError)
        assertFalse(state.showSaveError)
        assertFalse(state.hasName)
        assertNull(state.toDraftOrNull())
    }

    @Test
    fun `blank name or zone shows its error and builds no draft`() {
        listOf("", "   ", "\n\t").forEach { blank ->
            val blankName = AddLandState(name = blank, zone = "El Llano")
                .reduce(AddLandAction.SaveClicked)
            assertTrue(blankName.showNameError)
            assertFalse(blankName.showZoneError)
            assertNull(blankName.toDraftOrNull())
            assertEquals(blank, blankName.name, "raw text must stay available for correction")

            val blankZone = AddLandState(name = "Los Olivos", zone = blank)
                .reduce(AddLandAction.SaveClicked)
            assertFalse(blankZone.showNameError)
            assertTrue(blankZone.showZoneError)
            assertEquals(ZoneProblem.BLANK, blankZone.zoneIssue)
            assertNull(blankZone.toDraftOrNull())
            assertEquals(blank, blankZone.zone, "raw text must stay available for correction")
        }
    }

    @Test
    fun `an over-long zone is rejected while a trimmed valid zone is saved`() {
        val tooLong = AddLandState(name = "Los Olivos", zone = "x".repeat(ZONE_MAX_LENGTH + 1))
            .reduce(AddLandAction.SaveClicked)

        assertTrue(tooLong.showZoneError)
        assertEquals(ZoneProblem.TOO_LONG, tooLong.zoneIssue)
        assertNull(tooLong.toDraftOrNull())

        val state = AddLandState(name = "  Los Olivos  ", zone = "  El Llano  ")
            .reduce(AddLandAction.SaveClicked)

        assertFalse(state.showNameError)
        assertFalse(state.showZoneError)
        assertFalse(state.showSaveError)
        val draft = state.toDraftOrNull()
        assertEquals(
            LandDraft(
                name = "Los Olivos",
                zone = "El Llano",
                municipality = null,
                waterRegime = WaterRegime.UNKNOWN,
                productionMethod = ProductionMethod.UNKNOWN,
                variety = LandVariety.UNKNOWN,
                varietyOther = null,
                areaHectares = null,
                treeCount = null,
                notes = null,
            ),
            draft,
        )
    }

    @Test
    fun `name and zone only land is saved with unknown attributes and survives reopening`() {
        val storage = MemoryStorage()
        val state = AddLandState(name = "  Los Olivos  ", zone = "  El Llano  ")
        val draft = state.reduce(AddLandAction.SaveClicked).toDraftOrNull()!!
        val saved = repository(storage).create(draft, now = 1)

        assertEquals("Los Olivos", saved.name)
        assertEquals("El Llano", saved.zone)
        assertNull(saved.municipality)
        assertEquals(WaterRegime.UNKNOWN, saved.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, saved.productionMethod)
        assertEquals(LandVariety.UNKNOWN, saved.variety)
        assertNull(saved.varietyOther)
        assertNull(saved.areaHectares)
        assertNull(saved.treeCount)
        assertNull(saved.notes)
        assertEquals(listOf(saved), repository(storage).list())
    }

    @Test
    fun `known water production and variety selections map to their enums`() {
        val storage = MemoryStorage()
        val state = AddLandState(
            name = "La Loma",
            zone = "Linde del arroyo",
            municipality = "  Martos ",
            waterRegime = WaterRegime.DRYLAND,
            productionMethod = ProductionMethod.CONVENTIONAL,
        ).reduce(AddLandAction.WaterRegimeSelected(WaterRegime.IRRIGATED))
            .reduce(AddLandAction.ProductionMethodSelected(ProductionMethod.ORGANIC))
            .reduce(AddLandAction.VarietySelected(LandVariety.HOJIBLANCA))

        val saved = repository(storage).create(state.toDraftOrNull()!!, now = 2)

        assertEquals(WaterRegime.IRRIGATED, saved.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, saved.productionMethod)
        assertEquals(LandVariety.HOJIBLANCA, saved.variety)
        assertEquals("Martos", saved.municipality)
        assertEquals(listOf(saved), repository(storage).list())
    }

    @Test
    fun `mixed selections stay deliberate instead of becoming unknown`() {
        val state = AddLandState(name = "Olivar viejo", zone = "El Llano")
            .reduce(AddLandAction.WaterRegimeSelected(WaterRegime.MIXED))
            .reduce(AddLandAction.ProductionMethodSelected(ProductionMethod.MIXED))
            .reduce(AddLandAction.VarietySelected(LandVariety.MIXED))

        val draft = state.toDraftOrNull()!!
        assertEquals(WaterRegime.MIXED, draft.waterRegime)
        assertEquals(ProductionMethod.MIXED, draft.productionMethod)
        assertEquals(LandVariety.MIXED, draft.variety)
    }

    @Test
    fun `custom variety requires text and keeps it only for Otra`() {
        val missing = AddLandState(
            name = "La Loma",
            zone = "El Llano",
            variety = LandVariety.OTHER,
            varietyOther = "   ",
        ).reduce(AddLandAction.SaveClicked)

        assertTrue(missing.showVarietyOtherError)
        assertNull(missing.toDraftOrNull(), "Otra without text must not be saved")

        val corrected = missing.reduce(AddLandAction.VarietyOtherChanged("  Royal de Cazorla  "))
        val other = corrected.toDraftOrNull()!!
        assertEquals(LandVariety.OTHER, other.variety)
        assertEquals("Royal de Cazorla", other.varietyOther)

        val shortlist = corrected
            .reduce(AddLandAction.VarietySelected(LandVariety.PICUAL))
            .toDraftOrNull()!!
        assertNull(shortlist.varietyOther, "switching away from Otra must clear stale text")
    }

    @Test
    fun `an over-long custom variety is rejected`() {
        val state = AddLandState(
            name = "La Loma",
            zone = "El Llano",
            variety = LandVariety.OTHER,
            varietyOther = "x".repeat(VARIETY_OTHER_MAX_LENGTH + 1),
        ).reduce(AddLandAction.SaveClicked)

        assertTrue(state.showVarietyOtherError)
        assertNull(state.toDraftOrNull())
    }

    @Test
    fun `valid measures are parsed and invalid measures keep their raw text`() {
        val saved = AddLandState(
            name = "La Loma",
            zone = "El Llano",
            areaText = " 1,5 ",
            treeCountText = " 85 ",
        ).reduce(AddLandAction.SaveClicked).toDraftOrNull()!!
        assertEquals(1.5, saved.areaHectares)
        assertEquals(85, saved.treeCount)

        listOf("letras", "-1", "1,234", "1,2,3").forEach { raw ->
            val state = AddLandState(
                name = "La Loma",
                zone = "El Llano",
                areaText = raw,
                treeCountText = "85",
            ).reduce(AddLandAction.SaveClicked)

            assertTrue(state.showAreaError, "expected a surface error for <$raw>")
            assertNull(state.toDraftOrNull())
            assertEquals(raw, state.areaText, "raw text must stay available for correction")
        }

        listOf("0", "-1", "1,5", "árbol").forEach { raw ->
            val state = AddLandState(
                name = "La Loma",
                zone = "El Llano",
                areaText = "1,5",
                treeCountText = raw,
            ).reduce(AddLandAction.SaveClicked)

            assertTrue(state.showTreeCountError, "expected a tree error for <$raw>")
            assertNull(state.toDraftOrNull())
            assertEquals(raw, state.treeCountText, "raw text must stay available for correction")
        }
    }

    @Test
    fun `two lands saved from the form both survive reopening`() {
        val storage = MemoryStorage()
        val nameOnly = AddLandState(name = "Los Olivos", zone = "El Llano")
            .toDraftOrNull()!!
        val known = AddLandState(
            name = "La Loma",
            zone = "La Vega",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            variety = LandVariety.PICUAL,
            areaText = "2,5",
            treeCountText = "85",
        ).toDraftOrNull()!!

        repository(storage).create(nameOnly, now = 1)
        repository(storage).create(known, now = 2)

        val reopened = repository(storage).list()
        assertEquals(listOf("Los Olivos", "La Loma"), reopened.map { it.name })
        assertEquals(WaterRegime.UNKNOWN, reopened[0].waterRegime)
        assertEquals(WaterRegime.IRRIGATED, reopened[1].waterRegime)
        assertEquals(ProductionMethod.ORGANIC, reopened[1].productionMethod)
        assertEquals(2.5, reopened[1].areaHectares)
        assertEquals(85, reopened[1].treeCount)
    }

    @Test
    fun `unicode name and zone are preserved`() {
        val state = AddLandState(
            name = "  Olivar 😀 de la Peña  ",
            zone = "  Cañada de la Encina  ",
        )

        val saved = repository(MemoryStorage()).create(state.toDraftOrNull()!!, now = 3)

        assertEquals("Olivar 😀 de la Peña", saved.name)
        assertEquals("Cañada de la Encina", saved.zone)
    }

    @Test
    fun `failed save keeps values, shows plain error, and allows retry`() {
        val state = AddLandState(
            name = "La Loma",
            zone = "El Llano",
            municipality = "Jaén",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            variety = LandVariety.ARBEQUINA,
            areaText = "1,5",
            treeCountText = "85",
        )
        val draft = state.toDraftOrNull()!!

        val failed = runCatching { repository(FailingStorage()).create(draft, now = 4) }
        assertTrue(failed.isFailure)

        val afterFailure = state.reduce(AddLandAction.SaveFailed)
        assertTrue(afterFailure.showSaveError)
        assertFalse(afterFailure.showNameError)
        assertEquals("La Loma", afterFailure.name)
        assertEquals("El Llano", afterFailure.zone)
        assertEquals("Jaén", afterFailure.municipality)
        assertEquals(WaterRegime.IRRIGATED, afterFailure.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, afterFailure.productionMethod)
        assertEquals(LandVariety.ARBEQUINA, afterFailure.variety)
        assertEquals("1,5", afterFailure.areaText)
        assertEquals("85", afterFailure.treeCountText)
        assertEquals(draft, afterFailure.toDraftOrNull())
    }

    @Test
    fun `editing a field clears previous errors`() {
        val failed = AddLandState(
            name = "La Loma",
            zone = "",
            showNameError = true,
            showZoneError = true,
            showAreaError = true,
            showTreeCountError = true,
            showSaveError = true,
        )

        val renamed = failed.reduce(AddLandAction.NameChanged("La Loma baja"))
        assertFalse(renamed.showNameError)
        assertFalse(renamed.showSaveError)

        assertFalse(failed.reduce(AddLandAction.ZoneChanged("El Llano")).showZoneError)
        assertFalse(failed.reduce(AddLandAction.MunicipalityChanged("Jaén")).showSaveError)
        assertFalse(
            failed.reduce(AddLandAction.WaterRegimeSelected(WaterRegime.DRYLAND)).showSaveError,
        )
        assertFalse(
            failed.reduce(AddLandAction.ProductionMethodSelected(ProductionMethod.MIXED)).showSaveError,
        )
        assertFalse(
            failed.reduce(AddLandAction.VarietySelected(LandVariety.PICUAL)).showVarietyOtherError,
        )
        assertFalse(failed.reduce(AddLandAction.VarietyOtherChanged("Otra")).showVarietyOtherError)
        assertFalse(failed.reduce(AddLandAction.AreaChanged("1,5")).showAreaError)
        assertFalse(failed.reduce(AddLandAction.TreeCountChanged("85")).showTreeCountError)
    }

    @Test
    fun `leaving the form without saving writes no record`() {
        val storage = MemoryStorage()
        val filled = AddLandState(name = "Los Olivos", zone = "El Llano")
            .reduce(AddLandAction.WaterRegimeSelected(WaterRegime.DRYLAND))

        // Filling the form is pure state: nothing reaches storage until "Guardar terreno" is used.
        assertEquals(emptyList(), repository(storage).list())

        // Leaving the form (cancel) resets to a fresh state with no draft to persist.
        val afterLeaving = AddLandState()
        assertNull(afterLeaving.toDraftOrNull())
        assertEquals("", afterLeaving.name)
        assertTrue(filled.toDraftOrNull() != null)
    }

    private fun repository(storage: LandStorage): LandRepository =
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

    private class FailingStorage : LandStorage {
        override fun read(): String? = null

        override fun write(value: String) {
            throw IllegalStateException("Could not persist local lands")
        }
    }
}
