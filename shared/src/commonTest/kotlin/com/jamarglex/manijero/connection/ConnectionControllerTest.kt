package com.jamarglex.manijero.connection

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

private const val DEFAULT_URL = "http://10.0.2.2:8000"
private const val LAN_URL = "http://192.168.1.20:8000"

/** A checker that records each call and answers when the test says so. */
private class ScriptedChecker(var result: ServiceCheckResult = ServiceCheckResult.Ready) : ServiceStatusChecker {
    val calls = mutableListOf<String>()
    var gate: CompletableDeferred<Unit>? = null
    var activeAtCall: String? = null
    var address: ActiveServiceAddress? = null

    override suspend fun check(baseUrl: String): ServiceCheckResult {
        calls += baseUrl
        activeAtCall = address?.current
        gate?.await()
        return result
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class ConnectionControllerTest {
    private fun setup(store: FakeAddressStore = FakeAddressStore()): Triple<ActiveServiceAddress, ScriptedChecker, FakeAddressStore> {
        val address = ActiveServiceAddress(DEFAULT_URL, store)
        val checker = ScriptedChecker().also { it.address = address }
        return Triple(address, checker, store)
    }

    @Test
    fun `opening shows the address in use and where it comes from`() = runTest {
        val (address, checker) = setup(FakeAddressStore(saved = LAN_URL))
        val controller = ConnectionController(address, checker, this)

        assertEquals(LAN_URL, controller.state.input)
        assertEquals(LAN_URL, controller.state.activeUrl)
        assertEquals(ServiceAddressSource.Saved, controller.state.activeSource)
        assertNull(controller.state.notice)
    }

    @Test
    fun `an invalid address makes no request and no save and keeps the typed text`() = runTest {
        val (address, checker, store) = setup()
        val controller = ConnectionController(address, checker, this)

        controller.onInputChange("192.168.1.20")
        controller.check()
        advanceUntilIdle()

        assertEquals(ConnectionNotice.INVALID_ADDRESS, controller.state.notice)
        assertEquals("192.168.1.20", controller.state.input)
        assertTrue(checker.calls.isEmpty())
        assertEquals(0, store.writes)
        assertEquals(DEFAULT_URL, address.current)
    }

    @Test
    fun `a valid address is saved and applied before it is checked`() = runTest {
        val (address, checker, store) = setup()
        val controller = ConnectionController(address, checker, this)

        controller.onInputChange("  $LAN_URL/ ")
        controller.check()
        assertTrue(controller.state.checking, "the check is running")
        advanceUntilIdle()

        assertEquals(listOf(LAN_URL), checker.calls)
        assertEquals(LAN_URL, checker.activeAtCall, "the address was in use before the check ran")
        assertEquals(LAN_URL, store.saved)
        assertEquals(LAN_URL, controller.state.input)
        assertEquals(ServiceAddressSource.Saved, controller.state.activeSource)
        assertFalse(controller.state.checking)
        assertEquals(ConnectionNotice.READY, controller.state.notice)
    }

    @Test
    fun `every check result maps to its own notice`() = runTest {
        val expected = mapOf(
            ServiceCheckResult.Ready to ConnectionNotice.READY,
            ServiceCheckResult.NotReady to ConnectionNotice.NOT_READY,
            ServiceCheckResult.ReadyUnknown to ConnectionNotice.READY_UNKNOWN,
            ServiceCheckResult.Unreachable to ConnectionNotice.UNREACHABLE,
            ServiceCheckResult.NotManijero to ConnectionNotice.NOT_MANIJERO,
        )
        assertEquals(ServiceCheckResult.entries.toSet(), expected.keys)
        expected.forEach { (result, notice) ->
            val (address, checker) = setup()
            checker.result = result
            val controller = ConnectionController(address, checker, this)
            controller.onInputChange(LAN_URL)
            controller.check()
            advanceUntilIdle()
            assertEquals(notice, controller.state.notice)
        }
    }

    @Test
    fun `a refused save stops before the check and keeps the address in use`() = runTest {
        val (address, checker, store) = setup(FakeAddressStore(failWrites = true))
        val controller = ConnectionController(address, checker, this)

        controller.onInputChange(LAN_URL)
        controller.check()
        advanceUntilIdle()

        assertEquals(ConnectionNotice.STORAGE_FAILED, controller.state.notice)
        assertTrue(checker.calls.isEmpty())
        assertNull(store.saved)
        assertEquals(DEFAULT_URL, address.current)
        assertEquals(DEFAULT_URL, controller.state.activeUrl)
        assertEquals(LAN_URL, controller.state.input, "the typed text stays for a retry")
    }

    @Test
    fun `buttons are disabled while checking and a second press is ignored`() = runTest {
        val (address, checker, store) = setup(FakeAddressStore(saved = LAN_URL))
        checker.gate = CompletableDeferred()
        val controller = ConnectionController(address, checker, this)

        controller.check()
        runCurrent()
        assertTrue(controller.state.checking)
        val writesDuringCheck = store.writes

        controller.onInputChange("http://10.0.0.9:8000")
        controller.check()
        controller.resetToDefault()
        runCurrent()

        assertEquals(1, checker.calls.size, "a second press starts no second check")
        assertEquals(writesDuringCheck, store.writes, "neither press nor reset writes while checking")
        assertEquals(LAN_URL, address.current)

        checker.gate?.complete(Unit)
        advanceUntilIdle()
        assertFalse(controller.state.checking)
    }

    @Test
    fun `reset deletes the saved address and announces the default`() = runTest {
        val (address, checker, store) = setup(FakeAddressStore(saved = LAN_URL))
        val controller = ConnectionController(address, checker, this)

        controller.resetToDefault()

        assertNull(store.saved)
        assertEquals(DEFAULT_URL, address.current)
        assertEquals(DEFAULT_URL, controller.state.input)
        assertEquals(DEFAULT_URL, controller.state.activeUrl)
        assertEquals(ServiceAddressSource.Default, controller.state.activeSource)
        assertEquals(ConnectionNotice.RESET_TO_DEFAULT, controller.state.notice)
        assertTrue(checker.calls.isEmpty(), "a reset makes no request")
    }

    @Test
    fun `a refused reset keeps the saved address in use`() = runTest {
        val store = FakeAddressStore(saved = LAN_URL)
        val (address, checker) = setup(store)
        val controller = ConnectionController(address, checker, this)
        store.failWrites = true

        controller.resetToDefault()

        assertEquals(ConnectionNotice.STORAGE_FAILED, controller.state.notice)
        assertEquals(LAN_URL, address.current)
        assertEquals(ServiceAddressSource.Saved, controller.state.activeSource)
    }

    @Test
    fun `leaving the screen cancels the check without a result`() = runTest {
        val (address, checker) = setup()
        checker.gate = CompletableDeferred()
        val controller = ConnectionController(address, checker, this)

        controller.onInputChange(LAN_URL)
        controller.check()
        runCurrent()
        controller.leave()
        advanceUntilIdle()

        assertFalse(controller.state.checking)
        assertNull(controller.state.notice)
        assertEquals(LAN_URL, address.current, "the saved address stays after leaving")
    }

    @Test
    fun `reopening drops an old message and shows the address in use`() = runTest {
        val (address, checker) = setup()
        val controller = ConnectionController(address, checker, this)
        controller.onInputChange("nope")
        controller.check()
        assertEquals(ConnectionNotice.INVALID_ADDRESS, controller.state.notice)

        controller.open()

        assertNull(controller.state.notice)
        assertEquals(DEFAULT_URL, controller.state.input)
    }
}
