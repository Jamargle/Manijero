package com.jamarglex.manijero.connection

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/**
 * Composition-scoped owner of the `Conexión` flow. It applies the pure [reduce] reducer and runs the
 * single in-flight check on [scope], so the screen never touches the store or the network itself.
 *
 * - [check] validates first (an invalid address makes no request and no save), then saves and
 *   applies the address, and only then checks it. A refused save stops before the check.
 * - [resetToDefault] deletes the saved address so the build default is used again.
 * - [leave] cancels a running check when the person leaves the screen.
 *
 * Nothing about the address or the result is logged.
 */
class ConnectionController(
    private val address: ActiveServiceAddress,
    private val checker: ServiceStatusChecker,
    private val scope: CoroutineScope,
) {
    var state: ConnectionState by mutableStateOf(openedState())
        private set

    private var job: Job? = null

    /** The screen was opened: show the address in use and drop any old message. */
    fun open() {
        if (!state.checking) state = openedState()
    }

    fun onInputChange(text: String) {
        state = state.reduce(ConnectionAction.InputChanged(text))
    }

    fun check() {
        if (state.checking) return
        val url = when (val parsed = normalizeServiceAddress(state.input)) {
            is ServiceAddressInput.Valid -> parsed.url
            ServiceAddressInput.Invalid -> {
                state = state.reduce(ConnectionAction.Refused(ConnectionNotice.INVALID_ADDRESS))
                return
            }
        }
        if (!address.save(url)) {
            state = state.reduce(ConnectionAction.Refused(ConnectionNotice.STORAGE_FAILED))
            return
        }
        state = state.reduce(ConnectionAction.CheckStarted(url))
        job = scope.launch {
            val result = try {
                checker.check(url)
            } catch (cancellation: CancellationException) {
                state = state.reduce(ConnectionAction.CheckCancelled)
                throw cancellation
            } catch (_: Exception) {
                ServiceCheckResult.Unreachable
            }
            state = state.reduce(ConnectionAction.CheckFinished(result))
        }
    }

    fun resetToDefault() {
        if (state.checking) return
        state = if (address.reset()) {
            state.reduce(ConnectionAction.ResetDone(address.current))
        } else {
            state.reduce(ConnectionAction.Refused(ConnectionNotice.STORAGE_FAILED))
        }
    }

    /** The person left the screen: stop a running check. The saved address stays. */
    fun leave() {
        job?.cancel()
        job = null
        if (state.checking) state = state.reduce(ConnectionAction.CheckCancelled)
    }

    private fun openedState(): ConnectionState =
        ConnectionState(input = "", activeUrl = "", activeSource = ServiceAddressSource.Default)
            .reduce(ConnectionAction.Opened(address.current, address.source))
}
