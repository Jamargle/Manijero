package com.jamarglex.manijero

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.jamarglex.manijero.chat.AnswerService
import com.jamarglex.manijero.chat.AnswerServiceUnavailableException
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.lands.Land
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * Composition-scoped owner of the chat conversation. It applies the pure [reduce]
 * reducer and runs the single in-flight submission on the injected scope, so the UI never
 * performs a network call itself and a screen that leaves the composition releases its
 * request.
 *
 * [landsProvider] is the read of the local land list used to build the request's land context. It is
 * invoked on every submit **and** every retry, so a land added, edited, or removed after the chat
 * screen opened is reflected in the next request. The default reads nothing, which keeps the accepted
 * `general` request for constructors that have no land store.
 */
class ChatConversation(
    private val answerService: AnswerService,
    private val scope: CoroutineScope,
    private val landsProvider: () -> List<Land> = { emptyList() },
) {
    var state: ChatHomeState by mutableStateOf(ChatHomeState())
        private set

    fun onAction(action: ChatHomeAction) {
        val reduction = state.reduce(action)
        state = reduction.state
        when (val effect = reduction.effect) {
            null -> Unit
            is ChatEffect.Submit -> scope.launch { submit(effect) }
        }
    }

    private suspend fun submit(effect: ChatEffect.Submit) {
        // A failing local read degrades to the accepted `general` request instead of turning a
        // question into a failure; the throwable is never logged or surfaced.
        val lands = runCatching { landsProvider() }.getOrElse { emptyList() }
        try {
            onAction(ChatHomeAction.ResponseReceived(answerService.ask(effect.request(lands))))
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (_: AnswerServiceUnavailableException) {
            // The service was not reached; nothing was answered.
            onAction(ChatHomeAction.RequestFailed(RequestFailure.COULD_NOT_REACH_SERVICE))
        } catch (_: Exception) {
            // Error status, unusable body, no service configured, or any other failure: the
            // exception text is never logged or shown, and no answer is invented.
            onAction(ChatHomeAction.RequestFailed(RequestFailure.SERVICE_ERROR))
        }
    }
}
