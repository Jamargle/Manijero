package com.jamarglex.manijero

import com.jamarglex.manijero.chat.AnswerService
import com.jamarglex.manijero.chat.AnswerServiceErrorException
import com.jamarglex.manijero.chat.AnswerServiceUnavailableException
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskRequest
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.chat.UnavailableAnswerService
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** The pinned code-owned `no_evidence` abstention message, taken verbatim from the accepted contract. */
private const val PINNED_NO_EVIDENCE =
    "No he encontrado esta información en los documentos oficiales que tengo. " +
        "Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."

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

    private fun abstainedResponse(answer: String = PINNED_NO_EVIDENCE) = AskResponse(
        status = AnswerStatus.abstained,
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

    /** Fails with [failures] in order, then answers; records every request it received. */
    private class ScriptedAnswerService(
        private val failures: List<Throwable>,
        private val answer: AskResponse,
    ) : AnswerService {
        val requests = mutableListOf<AskRequest>()

        override suspend fun ask(request: AskRequest): AskResponse {
            requests += request
            val attempt = requests.lastIndex
            if (attempt < failures.size) throw failures[attempt]
            return answer
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
    fun `an abstained response arrives once with its state and is never a failure`() = runTest {
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse = abstainedResponse()
        }
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.USER })
        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.ASSISTANT })
        val assistant = conversation.state.messages.single { it.speaker == Speaker.ASSISTANT }
        assertEquals(AnswerStatus.abstained, assistant.answerStatus)
        assertEquals(PINNED_NO_EVIDENCE, assistant.text)
        assertNull(conversation.state.failure)
        assertNull(conversation.state.failedQuestion)
        assertEquals(AnswerStatus.abstained, conversation.state.lastResponseStatus)
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
        assertEquals(RequestFailure.SERVICE_ERROR, conversation.state.failure)
        assertEquals(originalQuestion, conversation.state.failedQuestion)
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
        assertEquals(RequestFailure.SERVICE_ERROR, conversation.state.failure)
    }

    @Test
    fun `an unreachable service is reported as could not reach`() = runTest {
        val service = ScriptedAnswerService(
            failures = listOf(AnswerServiceUnavailableException()),
            answer = response(),
        )
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(RequestFailure.COULD_NOT_REACH_SERVICE, conversation.state.failure)
        assertEquals(originalQuestion, conversation.state.failedQuestion)
        assertEquals(originalQuestion, conversation.state.question)
        assertEquals(1, conversation.state.messages.size)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `a service error is reported as a service error`() = runTest {
        val service = ScriptedAnswerService(
            failures = listOf(AnswerServiceErrorException()),
            answer = response(),
        )
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(RequestFailure.SERVICE_ERROR, conversation.state.failure)
        assertEquals(originalQuestion, conversation.state.failedQuestion)
        assertEquals(1, conversation.state.messages.size)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `retry resends the exact wording and adds one user message and one answer`() = runTest {
        val gate = CompletableDeferred<AskResponse>()
        val requests = mutableListOf<AskRequest>()
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse {
                requests += request
                if (requests.size == 1) throw AnswerServiceUnavailableException()
                return gate.await()
            }
        }
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(1, requests.size)
        assertEquals(RequestFailure.COULD_NOT_REACH_SERVICE, conversation.state.failure)

        conversation.onAction(ChatHomeAction.RetryClicked)
        runCurrent()

        assertEquals(SubmissionPhase.SUBMITTING, conversation.state.phase)
        assertNull(conversation.state.failure)

        // While the retry is in flight the action is not actionable: no third request.
        val attemptsAfterRetry = requests.size
        conversation.onAction(ChatHomeAction.RetryClicked)
        runCurrent()
        assertEquals(attemptsAfterRetry, requests.size)
        assertEquals(SubmissionPhase.SUBMITTING, conversation.state.phase)

        gate.complete(response("Respuesta única."))
        advanceUntilIdle()

        assertEquals(2, requests.size)
        assertEquals(originalQuestion, requests.last().question)
        assertEquals(2, conversation.state.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), conversation.state.messages[0])
        assertEquals(ChatMessage(Speaker.ASSISTANT, "Respuesta única."), conversation.state.messages[1])
        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.USER })
        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.ASSISTANT })
        assertNull(conversation.state.failure)
        assertNull(conversation.state.failedQuestion)
        assertEquals("", conversation.state.question)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `a retry that fails again keeps one user message and stays retryable`() = runTest {
        val service = ScriptedAnswerService(
            failures = listOf(
                AnswerServiceErrorException(),
                AnswerServiceUnavailableException(),
            ),
            answer = response("Respuesta única."),
        )
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()
        conversation.onAction(ChatHomeAction.RetryClicked)
        advanceUntilIdle()

        assertEquals(2, service.requests.size)
        assertTrue(service.requests.all { it.question == originalQuestion })
        assertEquals(1, conversation.state.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), conversation.state.messages.single())
        assertEquals(RequestFailure.COULD_NOT_REACH_SERVICE, conversation.state.failure)
        assertEquals(originalQuestion, conversation.state.failedQuestion)
        assertEquals(originalQuestion, conversation.state.question)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)

        val thirdAttempt = conversation.state.reduce(ChatHomeAction.RetryClicked)
        assertEquals(SubmissionPhase.SUBMITTING, thirdAttempt.state.phase)
        assertEquals(originalQuestion, (thirdAttempt.effect as ChatEffect.Submit).question)
    }
}
