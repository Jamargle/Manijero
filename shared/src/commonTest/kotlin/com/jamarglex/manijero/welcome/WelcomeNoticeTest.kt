package com.jamarglex.manijero.welcome

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class WelcomeNoticeTest {
    private class FakeStore(
        var dismissed: Boolean = false,
        private val failRead: Boolean = false,
        private val failWrite: Boolean = false,
    ) : WelcomeNoticeStore {
        var writes = 0

        override fun isDismissed(): Boolean {
            if (failRead) error("read refused")
            return dismissed
        }

        override fun markDismissed() {
            if (failWrite) error("write refused")
            writes++
            dismissed = true
        }
    }

    @Test
    fun freshStoreShowsTheCard() = assertTrue(WelcomeNotice(FakeStore()).visible)

    @Test
    fun dismissedStoreHidesTheCard() = assertFalse(WelcomeNotice(FakeStore(dismissed = true)).visible)

    @Test
    fun dismissHidesAndWritesOnce() {
        val store = FakeStore()
        val notice = WelcomeNotice(store)
        notice.dismiss()
        assertFalse(notice.visible)
        assertEquals(1, store.writes)
        assertFalse(WelcomeNotice(store).visible)
    }

    @Test
    fun unreadableStoreShowsTheCard() = assertTrue(WelcomeNotice(FakeStore(failRead = true)).visible)

    @Test
    fun refusedWriteStillHidesForTheSession() {
        val store = FakeStore(failWrite = true)
        val notice = WelcomeNotice(store)
        notice.dismiss()
        assertFalse(notice.visible)
        assertTrue(WelcomeNotice(store).visible)
    }

    @Test
    fun showAgainWritesNothingAndDismissHidesAgain() {
        val store = FakeStore(dismissed = true)
        val notice = WelcomeNotice(store)
        notice.showAgain()
        assertTrue(notice.visible)
        assertEquals(0, store.writes)
        notice.dismiss()
        assertFalse(notice.visible)
    }
}
