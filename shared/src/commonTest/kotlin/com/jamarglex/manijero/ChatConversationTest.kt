package com.jamarglex.manijero

import com.jamarglex.manijero.chat.AnswerService
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskRequest
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.UnavailableAnswerService
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

@OptIn(ExperimentalCoroutinesApi::class)
class ChatConversationTest {
    private val originalQuestion = "  ¿Puedo regar hoy?  "

    private fun response(answer: String = "Una respuesta.") = AskResponse(
        status = AnswerStatus.answered,
        answer = answer,
        sources = emptyList(),
        land_scope = LandContextMode.general,
        land_ids_to_choose = emptyList(),
    )

    private class GatedAnswerService : AnswerService {
        val requests = mutableListOf<AskRequest>()
        private val gate = CompletableDeferred<AskResponse>()

        override suspend fun ask(request: AskRequest): AskResponse {
            requests += request
            return gate.await()
        }

        fun complete(response: AskResponse) {
            gate.complete(response)
        }
    }

    @Test
    fun `repeated clicks produce one request and one reply`() = runTest {
        val service = GatedAnswerService()
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        runCurrent()
        conversation.onAction(ChatHomeAction.AskClicked)
        runCurrent()

        assertEquals(1, service.requests.size)
        assertEquals(originalQuestion, service.requests.single().question)
        assertEquals(SubmissionPhase.SUBMITTING, conversation.state.phase)

        service.complete(response("Respuesta única."))
        advanceUntilIdle()

        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.ASSISTANT })
        assertEquals("Respuesta única.", conversation.state.messages.last().text)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `a transport failure releases the composer without inventing a reply`() = runTest {
        val failingService = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse =
                error("no answer endpoint is configured")
        }
        val conversation = ChatConversation(failingService, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
        assertEquals(originalQuestion, conversation.state.question)
        assertEquals(1, conversation.state.messages.size)
        assertNull(conversation.state.lastResponseStatus)
    }

    @Test
    fun `the default wiring fails instead of fabricating an answer`() = runTest {
        val conversation = ChatConversation(UnavailableAnswerService, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(1, conversation.state.messages.size)
        assertEquals(originalQuestion, conversation.state.question)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }
}
