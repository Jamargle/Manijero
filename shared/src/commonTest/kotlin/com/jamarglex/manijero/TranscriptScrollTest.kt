package com.jamarglex.manijero

import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.RequestFailure
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/**
 * The transcript scroll key decides *when* the chat home brings the newest content into view. It must
 * change for every appended element and for nothing else: a keystroke, an example selection, or any
 * unrelated recomposition must leave it equal so nothing scrolls.
 */
class TranscriptScrollTest {
    private val question = "¿Puedo regar hoy?"

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

    private fun typed(text: String) =
        ChatHomeState().reduce(ChatHomeAction.QuestionChanged(text)).state

    private fun submitting(text: String = question) =
        typed(text).reduce(ChatHomeAction.AskClicked).state

    private fun ChatHomeState.key() = transcriptScrollKey(this)

    @Test
    fun `key changes when a user entry is appended`() {
        val typedState = typed(question)
        val submittingState = submitting()

        assertNotEquals(typedState.key(), submittingState.key())
        assertEquals(0, typedState.key().entryCount)
        assertEquals(1, submittingState.key().entryCount)
    }

    @Test
    fun `key changes when the working indication appears`() {
        val idle = typed(question)
        val working = submitting()

        assertEquals(SubmissionPhase.IDLE, idle.key().phase)
        assertEquals(SubmissionPhase.SUBMITTING, working.key().phase)
        assertNotEquals(idle.key(), working.key())
    }

    @Test
    fun `key changes when an assistant entry is appended`() {
        val working = submitting()
        val answered = working.reduce(ChatHomeAction.ResponseReceived(response())).state

        assertEquals(1, working.key().entryCount)
        assertEquals(2, answered.key().entryCount)
        assertNotEquals(working.key(), answered.key())
    }

    @Test
    fun `key changes when a failure appears and again when it clears`() {
        val working = submitting()
        val failed = working
            .reduce(ChatHomeAction.RequestFailed(RequestFailure.SERVICE_ERROR)).state
        val retried = failed.reduce(ChatHomeAction.RetryClicked).state

        assertFalse(working.key().hasFailure)
        assertTrue(failed.key().hasFailure)
        assertNotEquals(working.key(), failed.key())
        assertFalse(retried.key().hasFailure)
        assertNotEquals(failed.key(), retried.key())
    }

    @Test
    fun `key changes when a clarification appears`() {
        val working = submitting()
        val clarification = working.reduce(
            ChatHomeAction.ResponseReceived(
                response(
                    status = AnswerStatus.needs_land_clarification,
                    answer = "",
                    landIds = listOf("land-1", "land-2"),
                ),
            ),
        ).state

        // A clarification appends no entry and is not a failure, so the chooser is the only change.
        assertFalse(working.key().awaitingLandClarification)
        assertFalse(working.key().hasFailure)
        assertTrue(clarification.key().awaitingLandClarification)
        assertFalse(clarification.key().hasFailure)
        assertEquals(working.key().entryCount, clarification.key().entryCount)
        assertNotEquals(working.key(), clarification.key())

        // Resubmitting the choice turns the working indication back on, so it moves again.
        val resubmitting = clarification
            .reduce(ChatHomeAction.LandChoiceSubmitted(listOf("land-1"))).state
        assertEquals(SubmissionPhase.SUBMITTING, resubmitting.key().phase)
        assertNotEquals(clarification.key(), resubmitting.key())
    }

    @Test
    fun `key does not change for a keystroke`() {
        val empty = ChatHomeState()
        val typedOnce = typed("¿")
        val typedTwice = typedOnce.reduce(ChatHomeAction.QuestionChanged("¿Puedo regar hoy?")).state

        assertEquals(empty.key(), typedOnce.key())
        assertEquals(typedOnce.key(), typedTwice.key())
    }

    @Test
    fun `key does not change for an example selection`() {
        val empty = ChatHomeState()
        val selected = empty
            .reduce(ChatHomeAction.SuggestedQuestionSelected("¿Puedo regar hoy?")).state

        assertEquals(empty.key(), selected.key())
    }

    @Test
    fun `key does not change for an equal-state re-reduce`() {
        val empty = ChatHomeState()
        // Not actionable: no effect and a byte-identical state, so nothing may scroll.
        val reducedAgain = empty.reduce(ChatHomeAction.AskClicked)

        assertEquals(empty, reducedAgain.state)
        assertEquals(empty.key(), reducedAgain.state.key())

        // A late response is refused exactly like a recomposition of the same state.
        val answered = submitting().reduce(ChatHomeAction.ResponseReceived(response())).state
        val lateResponse = answered.reduce(ChatHomeAction.ResponseReceived(response())).state

        assertEquals(answered, lateResponse)
        assertEquals(answered.key(), lateResponse.key())
    }
}
