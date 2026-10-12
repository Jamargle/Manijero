package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class AddLandStateTest {
    @Test
    fun `default form offers unknown for water and production`() {
        val state = AddLandState()

        assertEquals(WaterRegime.UNKNOWN, state.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, state.productionMethod)
        assertFalse(state.showNameError)
        assertFalse(state.showSaveError)
        assertFalse(state.hasName)
        assertNull(state.toDraftOrNull())
    }

    @Test
    fun `blank name shows error and builds no draft`() {
        listOf("", "   ", "\n\t").forEach { blank ->
            val state = AddLandState(name = blank).reduce(AddLandAction.SaveClicked)

            assertTrue(state.showNameError)
            assertFalse(state.showSaveError)
            assertNull(state.toDraftOrNull())
            assertEquals(blank, state.name, "raw text must stay available for correction")
        }
    }

    @Test
    fun `valid save clears errors and drafts a trimmed name without duplicates of repository rules`() {
        val state = AddLandState(
            name = "  Los Olivos  ",
            waterRegime = WaterRegime.UNKNOWN,
            productionMethod = ProductionMethod.UNKNOWN,
        ).reduce(AddLandAction.SaveClicked)

        assertFalse(state.showNameError)
        assertFalse(state.showSaveError)
        val draft = state.toDraftOrNull()
        assertEquals(
            LandDraft(
                name = "Los Olivos",
                municipality = null,
                waterRegime = WaterRegime.UNKNOWN,
                productionMethod = ProductionMethod.UNKNOWN,
                areaHectares = null,
                notes = null,
            ),
            draft,
        )
    }

    @Test
    fun `name only land is saved with unknown attributes and survives reopening`() {
        val storage = MemoryStorage()
        val state = AddLandState(name = "  Los Olivos  ")
        val draft = state.reduce(AddLandAction.SaveClicked).toDraftOrNull()!!
        val saved = repository(storage).create(draft, now = 1)

        assertEquals("Los Olivos", saved.name)
        assertNull(saved.municipality)
        assertEquals(WaterRegime.UNKNOWN, saved.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, saved.productionMethod)
        assertNull(saved.areaHectares)
        assertNull(saved.notes)
        assertEquals(listOf(saved), repository(storage).list())
    }

    @Test
    fun `known water and production selections map to their enums`() {
        val storage = MemoryStorage()
        val state = AddLandState(
            name = "La Loma",
            municipality = "  Martos ",
            waterRegime = WaterRegime.DRYLAND,
            productionMethod = ProductionMethod.CONVENTIONAL,
        ).reduce(AddLandAction.WaterRegimeSelected(WaterRegime.IRRIGATED))
            .reduce(AddLandAction.ProductionMethodSelected(ProductionMethod.ORGANIC))

        val saved = repository(storage).create(state.toDraftOrNull()!!, now = 2)

        assertEquals(WaterRegime.IRRIGATED, saved.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, saved.productionMethod)
        assertEquals("Martos", saved.municipality)
        assertEquals(listOf(saved), repository(storage).list())
    }

    @Test
    fun `mixed selections stay deliberate instead of becoming unknown`() {
        val state = AddLandState(name = "Olivar viejo")
            .reduce(AddLandAction.WaterRegimeSelected(WaterRegime.MIXED))
            .reduce(AddLandAction.ProductionMethodSelected(ProductionMethod.MIXED))

        val draft = state.toDraftOrNull()!!
        assertEquals(WaterRegime.MIXED, draft.waterRegime)
        assertEquals(ProductionMethod.MIXED, draft.productionMethod)
    }

    @Test
    fun `two lands saved from the form both survive reopening`() {
        val storage = MemoryStorage()
        val nameOnly = AddLandState(name = "Los Olivos").toDraftOrNull()!!
        val known = AddLandState(
            name = "La Loma",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
        ).toDraftOrNull()!!

        repository(storage).create(nameOnly, now = 1)
        repository(storage).create(known, now = 2)

        val reopened = repository(storage).list()
        assertEquals(listOf("Los Olivos", "La Loma"), reopened.map { it.name })
        assertEquals(WaterRegime.UNKNOWN, reopened[0].waterRegime)
        assertEquals(WaterRegime.IRRIGATED, reopened[1].waterRegime)
        assertEquals(ProductionMethod.ORGANIC, reopened[1].productionMethod)
    }

    @Test
    fun `unicode name is preserved`() {
        val state = AddLandState(name = "  Olivar 😀 de la Peña  ")

        val saved = repository(MemoryStorage()).create(state.toDraftOrNull()!!, now = 3)

        assertEquals("Olivar 😀 de la Peña", saved.name)
    }

    @Test
    fun `failed save keeps values, shows plain error, and allows retry`() {
        val state = AddLandState(
            name = "La Loma",
            municipality = "Jaén",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
        )
        val draft = state.toDraftOrNull()!!

        val failed = runCatching { repository(FailingStorage()).create(draft, now = 4) }
        assertTrue(failed.isFailure)

        val afterFailure = state.reduce(AddLandAction.SaveFailed)
        assertTrue(afterFailure.showSaveError)
        assertFalse(afterFailure.showNameError)
        assertEquals("La Loma", afterFailure.name)
        assertEquals("Jaén", afterFailure.municipality)
        assertEquals(WaterRegime.IRRIGATED, afterFailure.waterRegime)
        assertEquals(ProductionMethod.ORGANIC, afterFailure.productionMethod)
        assertEquals(draft, afterFailure.toDraftOrNull())
    }

    @Test
    fun `editing a field clears previous errors`() {
        val failed = AddLandState(name = "La Loma", showNameError = true, showSaveError = true)

        val renamed = failed.reduce(AddLandAction.NameChanged("La Loma baja"))
        assertFalse(renamed.showNameError)
        assertFalse(renamed.showSaveError)

        assertFalse(failed.reduce(AddLandAction.MunicipalityChanged("Jaén")).showSaveError)
        assertFalse(
            failed.reduce(AddLandAction.WaterRegimeSelected(WaterRegime.DRYLAND)).showSaveError,
        )
        assertFalse(
            failed.reduce(AddLandAction.ProductionMethodSelected(ProductionMethod.MIXED)).showSaveError,
        )
    }

    @Test
    fun `leaving the form without saving writes no record`() {
        val storage = MemoryStorage()
        val filled = AddLandState(name = "Los Olivos")
            .reduce(AddLandAction.WaterRegimeSelected(WaterRegime.DRYLAND))

        // Filling the form is pure state: nothing reaches storage until "Guardar terreno" is used.
        assertEquals(emptyList(), repository(storage).list())

        // Leaving the form (cancel) resets to a fresh state with no draft to persist.
        val afterLeaving = AddLandState()
        assertNull(afterLeaving.toDraftOrNull())
        assertEquals("", afterLeaving.name)
        assertTrue(filled.toDraftOrNull() != null)
    }

    private fun repository(storage: LandStorage) = LandRepository(
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

    private class FailingStorage : LandStorage {
        override fun read(): String? = null
        override fun write(value: String) {
            throw IllegalStateException("Could not persist local lands")
        }
    }
}
