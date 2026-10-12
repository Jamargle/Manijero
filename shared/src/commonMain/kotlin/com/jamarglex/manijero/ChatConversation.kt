package com.jamarglex.manijero

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.jamarglex.manijero.chat.AnswerService
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * Composition-scoped owner of the chat conversation. It applies the pure [reduce]
 * reducer and runs the single in-flight submission on the injected scope, so the UI never
 * performs a network call itself and a screen that leaves the composition releases its
 * request.
 */
class ChatConversation(
    private val answerService: AnswerService,
    private val scope: CoroutineScope,
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
        try {
            onAction(ChatHomeAction.ResponseReceived(answerService.ask(effect.request())))
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (_: Exception) {
            // Failure copy and retry belong to the recovery feature; here the request
            // must only stop blocking the composer.
            onAction(ChatHomeAction.RequestFailed)
        }
    }
}
