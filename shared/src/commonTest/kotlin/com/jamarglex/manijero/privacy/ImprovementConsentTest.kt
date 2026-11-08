package com.jamarglex.manijero.privacy

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** The `Ayúdanos a mejorar` holder can only ever fail towards "off". */
class ImprovementConsentTest {
    private class FakeStore(
        var value: Boolean = false,
        val failRead: Boolean = false,
        val failWrite: Boolean = false,
    ) : ImprovementConsentStore {
        var writes = mutableListOf<Boolean>()
        override fun isEnabled(): Boolean = if (failRead) error("unreadable") else value
        override fun setEnabled(enabled: Boolean) {
            if (failWrite) error("refused")
            writes += enabled
            value = enabled
        }
    }

    @Test
    fun `no store and an empty store both start off`() {
        assertFalse(ImprovementConsent(null).enabled)
        assertFalse(ImprovementConsent(FakeStore()).enabled)
    }

    @Test
    fun `an unreadable store reads as off even if it would say on`() {
        assertFalse(ImprovementConsent(FakeStore(value = true, failRead = true)).enabled)
    }

    @Test
    fun `a saved on is read back and every change is written`() {
        val store = FakeStore(value = true)
        val consent = ImprovementConsent(store)
        assertTrue(consent.enabled)

        consent.update(false)
        consent.update(true)
        assertTrue(consent.enabled)
        assertEquals(listOf(false, true), store.writes)
    }

    @Test
    fun `a refused write still applies for this session without throwing`() {
        val consent = ImprovementConsent(FakeStore(failWrite = true))
        consent.update(true)
        assertTrue(consent.enabled)
    }
}
