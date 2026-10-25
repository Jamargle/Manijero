package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class LandListStateTest {
    @Test
    fun `empty successful load is the empty state`() {
        val default = LandListState()
        val loaded = LandListState().reduce(LandListAction.LandsLoaded(emptyList()))

        assertEquals(emptyList(), default.lands)
        assertTrue(default.isEmpty)
        assertFalse(default.loadFailed)

        assertEquals(emptyList(), loaded.lands)
        assertTrue(loaded.isEmpty)
        assertFalse(loaded.loadFailed)
    }

    @Test
    fun `load keeps repository order duplicate names and identities`() {
        val first = land("land-1", "Los Olivos")
        val duplicateName = land("land-2", "Los Olivos", municipality = "Martos")
        val third = land(
            "land-3",
            "La Loma",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
        )

        val state = LandListState()
            .reduce(LandListAction.LandsLoaded(listOf(first, duplicateName, third)))

        assertEquals(listOf(first, duplicateName, third), state.lands)
        assertEquals(listOf("land-1", "land-2", "land-3"), state.lands.map { it.id })
        assertEquals(listOf("Los Olivos", "Los Olivos", "La Loma"), state.lands.map { it.name })
        assertFalse(state.loadFailed)
        assertFalse(state.isEmpty)
    }

    @Test
    fun `failed load discards previous rows and is not empty`() {
        val loaded = LandListState()
            .reduce(LandListAction.LandsLoaded(listOf(land("land-1", "Los Olivos"))))

        val failed = loaded.reduce(LandListAction.LoadFailed)

        assertTrue(failed.loadFailed)
        assertFalse(failed.isEmpty)
        assertTrue(failed.lands.isEmpty(), "stale rows must not survive a failed reload")
    }

    @Test
    fun `a successful load after a failure clears the failure and is not stale`() {
        val recovered = LandListState(loadFailed = true)
            .reduce(LandListAction.LandsLoaded(listOf(land("land-1", "La Loma"))))

        assertFalse(recovered.loadFailed)
        assertEquals(listOf("La Loma"), recovered.lands.map { it.name })
        assertFalse(recovered.isEmpty)
    }

    @Test
    fun `reload clears the previous failure and rows`() {
        val afterFailure = LandListState(loadFailed = true).reduce(LandListAction.ReloadClicked)
        assertFalse(afterFailure.loadFailed)
        assertTrue(afterFailure.lands.isEmpty())
        assertTrue(afterFailure.isEmpty)

        val afterRows = LandListState()
            .reduce(LandListAction.LandsLoaded(listOf(land("land-1", "Los Olivos"))))
            .reduce(LandListAction.ReloadClicked)

        assertFalse(afterRows.loadFailed)
        assertTrue(afterRows.lands.isEmpty())
        assertTrue(afterRows.isEmpty)
    }

    @Test
    fun `changing the query keeps the lands and their order`() {
        val lands = listOf(
            land("land-1", "Los Olivos"),
            land("land-2", "La Loma", municipality = "Úbeda"),
        )
        val loaded = LandListState().reduce(LandListAction.LandsLoaded(lands))

        val searching = loaded.reduce(LandListAction.QueryChanged("loma"))

        assertEquals("loma", searching.query)
        assertEquals(lands, searching.lands)
        assertEquals(listOf("land-1", "land-2"), searching.lands.map { it.id })
        assertFalse(searching.loadFailed)
        assertFalse(searching.isEmpty, "a query never empties the list of saved lands")
    }

    @Test
    fun `a successful load after a query starts from a blank query`() {
        val searching = LandListState()
            .reduce(LandListAction.LandsLoaded(listOf(land("land-1", "Los Olivos"))))
            .reduce(LandListAction.QueryChanged("zzz"))

        val reloaded = searching.reduce(
            LandListAction.LandsLoaded(listOf(land("land-1", "Los Olivos"), land("land-2", "La Loma"))),
        )

        assertEquals("", reloaded.query)
        assertEquals(listOf("land-1", "land-2"), reloaded.lands.map { it.id })
    }

    @Test
    fun `a failed load after a query clears the query`() {
        val failed = LandListState()
            .reduce(LandListAction.LandsLoaded(listOf(land("land-1", "Los Olivos"))))
            .reduce(LandListAction.QueryChanged("olivos"))
            .reduce(LandListAction.LoadFailed)

        assertTrue(failed.loadFailed)
        assertEquals("", failed.query)
        assertTrue(failed.lands.isEmpty())
    }

    @Test
    fun `a reload clears the query`() {
        val reloaded = LandListState()
            .reduce(LandListAction.LandsLoaded(listOf(land("land-1", "Los Olivos"))))
            .reduce(LandListAction.QueryChanged("olivos"))
            .reduce(LandListAction.ReloadClicked)

        assertEquals("", reloaded.query)
        assertTrue(reloaded.lands.isEmpty())
        assertTrue(reloaded.isEmpty)
    }

    @Test
    fun `unicode long and emoji names survive verbatim`() {
        val names = listOf(
            "Olivar 😀 de la Peña",
            "El olivar de mi abuelo junto al camino de la fuente",
            "Los Olivos",
            "Olivar 😀 de la Peña",
        )

        val lands = names.mapIndexed { index, name -> land("land-$index", name) }

        val state = LandListState().reduce(LandListAction.LandsLoaded(lands))

        assertEquals(names, state.lands.map { it.name })
        assertEquals(4, state.lands.size, "a repeated name must stay as its own row")
    }

    private fun land(
        id: String,
        name: String,
        municipality: String? = null,
        waterRegime: WaterRegime = WaterRegime.UNKNOWN,
        productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    ) = Land(
        id = id,
        name = name,
        zone = "El Llano",
        municipality = municipality,
        waterRegime = waterRegime,
        productionMethod = productionMethod,
        createdAtEpochMillis = 0,
        updatedAtEpochMillis = 0,
    )
}
