package com.jamarglex.manijero

import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.MAX_QUESTION_LENGTH
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ChatHomeStateTest {
    private val originalQuestion = "  ¿Puedo regar hoy?  "

    private fun response(
        status: AnswerStatus = AnswerStatus.answered,
        answer: String = "Una respuesta.",
        landIds: List<String> = emptyList(),
    ) = AskResponse(
        status = status,
        answer = answer,
        sources = emptyList(),
        land_scope = LandContextMode.general,
        land_ids_to_choose = landIds,
    )

    private fun typed(question: String) =
        ChatHomeState().reduce(ChatHomeAction.QuestionChanged(question)).state

    private fun submitting(question: String = originalQuestion) =
        typed(question).reduce(ChatHomeAction.AskClicked).state

    @Test
    fun `blank question cannot be submitted`() {
        val state = typed(" \n\t")

        assertFalse(state.canAsk)
        val reduction = state.reduce(ChatHomeAction.AskClicked)
        assertNull(reduction.effect)
        assertTrue(reduction.state.messages.isEmpty())
        assertEquals(SubmissionPhase.IDLE, reduction.state.phase)
    }

    @Test
    fun `question over the contract limit cannot be submitted`() {
        val state = typed("a".repeat(MAX_QUESTION_LENGTH + 1))

        assertTrue(state.isOverCharacterLimit)
        assertFalse(state.canAsk)
        assertNull(state.reduce(ChatHomeAction.AskClicked).effect)
    }

    @Test
    fun `question at the contract limit can be submitted`() {
        val state = typed("a".repeat(MAX_QUESTION_LENGTH))

        assertFalse(state.isOverCharacterLimit)
        assertTrue(state.canAsk)
    }

    @Test
    fun `accepted question keeps exact wording and asks nothing else`() {
        val reduction = typed(originalQuestion).reduce(ChatHomeAction.AskClicked)

        assertEquals(originalQuestion, reduction.state.messages.single().text)
        assertEquals(Speaker.USER, reduction.state.messages.single().speaker)
        assertEquals("", reduction.state.question)
        assertEquals(SubmissionPhase.SUBMITTING, reduction.state.phase)

        val effect = reduction.effect as ChatEffect.Submit
        assertEquals(originalQuestion, effect.question)
        val request = effect.request()
        assertEquals(originalQuestion, request.question)
        assertEquals(LandContextMode.general, request.land_context.mode)
        assertTrue(request.land_context.lands.isEmpty())
    }

    @Test
    fun `a question is only sent once while the request is in flight`() {
        val inFlight = submitting()

        assertFalse(inFlight.canAsk)
        val duplicate = inFlight.reduce(ChatHomeAction.AskClicked)
        assertNull(duplicate.effect)
        assertEquals(1, duplicate.state.messages.size)
        assertEquals(SubmissionPhase.SUBMITTING, duplicate.state.phase)
    }

    @Test
    fun `a response becomes exactly one assistant message`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(response(answer = "Respuesta del servicio.")),
        ).state

        assertEquals(2, state.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), state.messages[0])
        assertEquals(ChatMessage(Speaker.ASSISTANT, "Respuesta del servicio."), state.messages[1])
        assertEquals(1, state.messages.count { it.speaker == Speaker.ASSISTANT })
        assertEquals(SubmissionPhase.IDLE, state.phase)
        assertNull(state.submittedQuestion)
    }

    @Test
    fun `a repeated response is not appended twice`() {
        val idle = submitting().reduce(
            ChatHomeAction.ResponseReceived(response(answer = "Primera.")),
        ).state

        val repeated = idle.reduce(ChatHomeAction.ResponseReceived(response(answer = "Segunda.")))

        assertEquals(1, repeated.state.messages.count { it.speaker == Speaker.ASSISTANT })
        assertEquals("Primera.", repeated.state.messages.last().text)
    }

    @Test
    fun `a later question can be submitted after a reply`() {
        val idle = submitting().reduce(
            ChatHomeAction.ResponseReceived(response()),
        ).state

        val next = idle.reduce(ChatHomeAction.QuestionChanged("¿Y ahora?"))

        assertTrue(next.state.canAsk)
        assertEquals(2, next.state.messages.size)
    }

    @Test
    fun `abstained answer is retained once without becoming a clarification`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(status = AnswerStatus.abstained, answer = "No puedo confirmarlo."),
            ),
        ).state

        assertEquals(AnswerStatus.abstained, state.lastResponseStatus)
        assertEquals("No puedo confirmarlo.", state.messages.last().text)
        assertFalse(state.awaitingLandClarification)
    }

    @Test
    fun `clarification keeps its ids and does not invent an answer`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(
                    status = AnswerStatus.needs_land_clarification,
                    answer = "",
                    landIds = listOf("land-001", "land-002"),
                ),
            ),
        ).state

        assertEquals(AnswerStatus.needs_land_clarification, state.lastResponseStatus)
        assertEquals(listOf("land-001", "land-002"), state.landIdsToChoose)
        assertEquals(1, state.messages.size)
        assertTrue(state.awaitingLandClarification)
    }

    @Test
    fun `a new submission clears the previous clarification state`() {
        val clarified = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(
                    status = AnswerStatus.needs_land_clarification,
                    answer = "",
                    landIds = listOf("land-001"),
                ),
            ),
        ).state

        val resubmitted = clarified
            .reduce(ChatHomeAction.QuestionChanged("¿Y en el otro?"))
            .state
            .reduce(ChatHomeAction.AskClicked)
            .state

        assertNull(resubmitted.lastResponseStatus)
        assertTrue(resubmitted.landIdsToChoose.isEmpty())
        assertFalse(resubmitted.awaitingLandClarification)
    }

    @Test
    fun `a failure releases the request keeping the wording available`() {
        val state = submitting().reduce(ChatHomeAction.RequestFailed).state

        assertEquals(SubmissionPhase.IDLE, state.phase)
        assertNull(state.submittedQuestion)
        assertEquals(originalQuestion, state.question)
        assertEquals(1, state.messages.size)
        assertNull(state.lastResponseStatus)
    }

    @Test
    fun `a failure does not overwrite a newly typed question`() {
        val state = submitting()
            .reduce(ChatHomeAction.QuestionChanged("Otra pregunta"))
            .state
            .reduce(ChatHomeAction.RequestFailed)
            .state

        assertEquals("Otra pregunta", state.question)
        assertEquals(SubmissionPhase.IDLE, state.phase)
    }
}
