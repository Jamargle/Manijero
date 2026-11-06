package com.jamarglex.manijero

import com.jamarglex.manijero.chat.AnswerRating
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.LandContextMode
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * The pure feedback rules of the chat reducer: only a finished, unrated answer accepts a tap; a
 * result applies only to the entry that is still sending that same rating; and no other state,
 * message or effect changes. It never sends anything and touches no transport.
 */
class AnswerFeedbackStateTest {
    private val answered = ChatMessage(Speaker.ASSISTANT, "Una respuesta.")
    private val abstained = ChatMessage(Speaker.ASSISTANT, "No puedo confirmarlo.", AnswerStatus.abstained)
    private val clarification = ChatMessage(
        Speaker.ASSISTANT,
        "Elige el terreno.",
        AnswerStatus.needs_land_clarification,
    )
    private val user = ChatMessage(Speaker.USER, "¿Puedo regar hoy?")

    private fun state() = ChatHomeState(
        messages = listOf(user, answered, abstained, clarification),
        phase = SubmissionPhase.IDLE,
        lastResponseStatus = AnswerStatus.answered,
        landIdsToChoose = emptyList(),
        retainNextQuestion = true,
    )

    private fun withFeedback(message: ChatMessage, feedback: AnswerFeedback) =
        state().copy(
            messages = state().messages.map { entry ->
                if (entry === message) entry.copy(feedback = feedback) else entry
            },
        )

    @Test
    fun `both decoded answer statuses accept a rating and only that entry becomes sending`() {
        val state = state()

        val answeredReduction = state.reduce(ChatHomeAction.FeedbackClicked(1, AnswerRating.USEFUL))
        assertEquals(ChatEffect.SendFeedback(1, AnswerRating.USEFUL), answeredReduction.effect)
        assertEquals(AnswerFeedback.Sending(AnswerRating.USEFUL), answeredReduction.state.messages[1].feedback)

        val abstainedReduction = state.reduce(ChatHomeAction.FeedbackClicked(2, AnswerRating.NOT_USEFUL))
        assertEquals(ChatEffect.SendFeedback(2, AnswerRating.NOT_USEFUL), abstainedReduction.effect)
        assertEquals(AnswerFeedback.Sending(AnswerRating.NOT_USEFUL), abstainedReduction.state.messages[2].feedback)
    }

    @Test
    fun `a rating tap changes nothing except the chosen entry's feedback`() {
        val state = state()
        val reduced = state.reduce(ChatHomeAction.FeedbackClicked(1, AnswerRating.USEFUL)).state

        assertEquals(
            state.copy(
                messages = state.messages.mapIndexed { index, message ->
                    if (index == 1) message.copy(feedback = AnswerFeedback.Sending(AnswerRating.USEFUL)) else message
                },
            ),
            reduced,
        )
        // The question, composer, retention choice, failure and clarification are untouched.
        assertEquals(state.question, reduced.question)
        assertEquals(state.phase, reduced.phase)
        assertEquals(state.retainNextQuestion, reduced.retainNextQuestion)
        assertEquals(state.failure, reduced.failure)
        assertEquals(state.failedQuestion, reduced.failedQuestion)
        assertEquals(state.clarificationQuestion, reduced.clarificationQuestion)
        assertEquals(state.landIdsToChoose, reduced.landIdsToChoose)
        assertEquals(state.lastResponseStatus, reduced.lastResponseStatus)
    }

    @Test
    fun `user and clarification entries and stale indices are identity with no effect`() {
        val state = state()
        listOf(-1, 0, 3, 4).forEach { index ->
            val reduction = state.reduce(ChatHomeAction.FeedbackClicked(index, AnswerRating.USEFUL))
            assertEquals(state, reduction.state, "index $index")
            assertNull(reduction.effect, "index $index")
        }
    }

    @Test
    fun `an entry already sending or sent never starts a second request`() {
        val sending = withFeedback(answered, AnswerFeedback.Sending(AnswerRating.USEFUL))
        val sendingAgain = sending.reduce(ChatHomeAction.FeedbackClicked(1, AnswerRating.NOT_USEFUL))
        assertEquals(sending, sendingAgain.state)
        assertNull(sendingAgain.effect)

        val sent = withFeedback(answered, AnswerFeedback.Sent(AnswerRating.USEFUL))
        val lockedReduction = sent.reduce(ChatHomeAction.FeedbackClicked(1, AnswerRating.NOT_USEFUL))
        assertEquals(sent, lockedReduction.state)
        assertNull(lockedReduction.effect)
    }

    @Test
    fun `a failed send is retryable with either rating`() {
        val failed = withFeedback(abstained, AnswerFeedback.Failed(AnswerRating.USEFUL))

        listOf(AnswerRating.NOT_USEFUL, AnswerRating.USEFUL).forEach { rating ->
            val retried = failed.reduce(ChatHomeAction.FeedbackClicked(2, rating))

            assertEquals(ChatEffect.SendFeedback(2, rating), retried.effect)
            assertEquals(AnswerFeedback.Sending(rating), retried.state.messages[2].feedback)
        }
    }

    @Test
    fun `a result settles only the entry still sending that same rating`() {
        val sending = state().reduce(ChatHomeAction.FeedbackClicked(1, AnswerRating.USEFUL)).state

        val received = sending.reduce(ChatHomeAction.FeedbackReceived(1, AnswerRating.USEFUL))
        assertEquals(AnswerFeedback.Sent(AnswerRating.USEFUL), received.state.messages[1].feedback)
        assertNull(received.effect)

        // A mismatched rating, a different entry, an already settled entry and a missing one are all
        // identity: no other answer is ever marked by a late result.
        listOf(
            ChatHomeAction.FeedbackReceived(1, AnswerRating.NOT_USEFUL),
            ChatHomeAction.FeedbackFailed(1, AnswerRating.NOT_USEFUL),
            ChatHomeAction.FeedbackReceived(2, AnswerRating.USEFUL),
            ChatHomeAction.FeedbackReceived(0, AnswerRating.USEFUL),
            ChatHomeAction.FeedbackReceived(9, AnswerRating.USEFUL),
            ChatHomeAction.FeedbackFailed(-1, AnswerRating.USEFUL),
        ).forEach { action ->
            val reduction = sending.reduce(action)
            assertEquals(sending, reduction.state, "$action")
            assertNull(reduction.effect, "$action")
        }

        val settled = received.state
        assertEquals(settled, settled.reduce(ChatHomeAction.FeedbackFailed(1, AnswerRating.USEFUL)).state)
    }

    @Test
    fun `a failure keeps both controls rateable and adds no transcript or failure state`() {
        val state = state()
        val sending = state.reduce(ChatHomeAction.FeedbackClicked(2, AnswerRating.NOT_USEFUL)).state
        val failed = sending.reduce(ChatHomeAction.FeedbackFailed(2, AnswerRating.NOT_USEFUL)).state

        assertEquals(AnswerFeedback.Failed(AnswerRating.NOT_USEFUL), failed.messages[2].feedback)
        assertEquals(state.messages.size, failed.messages.size)
        assertNull(failed.failure)
        assertNull(failed.failedQuestion)
        assertEquals(state.phase, failed.phase)

        // A retry is a fresh one-entry send, not a second answer or a second user message.
        val retried = failed.reduce(ChatHomeAction.FeedbackClicked(2, AnswerRating.USEFUL))
        assertEquals(ChatEffect.SendFeedback(2, AnswerRating.USEFUL), retried.effect)
        assertEquals(failed.messages.size, retried.state.messages.size)
        assertTrue(retried.state.messages[2].feedback is AnswerFeedback.Sending)
    }

    @Test
    fun `asking, retention and the question request are unchanged by the feedback effect`() {
        val asking = ChatHomeState(question = "¿Puedo regar hoy?", retainNextQuestion = true)
        val submit = asking.reduce(ChatHomeAction.AskClicked).effect as ChatEffect.Submit

        assertEquals("¿Puedo regar hoy?", submit.request(emptyList()).question)
        assertTrue(submit.request(emptyList()).retain_for_improvement)
        assertEquals(LandContextMode.general, submit.request(emptyList()).land_context.mode)
        // A feedback effect is not a question effect: it can never be turned into an `/ask` request.
        val feedbackEffect: ChatEffect = ChatEffect.SendFeedback(1, AnswerRating.USEFUL)
        assertTrue(feedbackEffect !is ChatEffect.QuestionEffect)
    }
}
