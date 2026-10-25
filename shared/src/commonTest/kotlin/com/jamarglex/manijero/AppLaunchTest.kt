package com.jamarglex.manijero

import com.jamarglex.manijero.lands.LandDraft
import com.jamarglex.manijero.lands.LandListState
import com.jamarglex.manijero.lands.LandRepository
import com.jamarglex.manijero.lands.LandStorage
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * The default `Mis terrenos` frame is hydrated once through the same guarded fold the repeatable
 * read uses, so it can be pinned without rendering: no store, an empty store, saved lands, and a
 * store that refuses to answer.
 */
class AppLaunchTest {

    @Test
    fun `no repository launches with an empty clean list`() {
        val state = initialLandListState(repository = null)

        assertEquals(LandListState(), state)
        assertTrue(state.isEmpty)
    }

    @Test
    fun `an empty store launches with the empty state`() {
        val state = initialLandListState(LandRepository(MemoryStorage()))

        assertEquals(LandListState(), state)
        assertTrue(state.isEmpty)
    }

    @Test
    fun `saved lands launch as already loaded`() {
        val storage = MemoryStorage()
        val repository = LandRepository(storage)
        val land = repository.create(LandDraft("La Loma"))

        val state = initialLandListState(repository)

        assertEquals(listOf(land), state.lands)
        assertFalse(state.loadFailed)
        assertFalse(state.isEmpty)
    }

    @Test
    fun `a refusing store launches as a failed read, never as empty`() {
        val state = initialLandListState(LandRepository(FailingStorage()))

        assertTrue(state.loadFailed)
        assertTrue(state.lands.isEmpty())
        assertFalse(state.isEmpty)
    }

    private class MemoryStorage : LandStorage {
        private var value: String? = null

        override fun read(): String? = value

        override fun write(value: String) {
            this.value = value
        }
    }

    private class FailingStorage : LandStorage {
        override fun read(): String? = error("storage unavailable")

        override fun write(value: String) = error("storage unavailable")
    }
}
