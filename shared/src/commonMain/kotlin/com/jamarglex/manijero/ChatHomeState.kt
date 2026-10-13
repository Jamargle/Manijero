package com.jamarglex.manijero

import com.jamarglex.manijero.chat.AnswerSource
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.MAX_QUESTION_LENGTH
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.chat.generalAskRequest

/**
 * Presentation state for one chat home screen. It is intentionally pure data: the only
 * way to advance it is [reduce], which also declares the work the caller has to run.
 *
 * [failure] and [failedQuestion] keep a failed request **outside** [messages], so a failure can
 * never be read as an assistant answer: the notice is rendered from state, and [failedQuestion]
 * is the exact wording [ChatHomeAction.RetryClicked] resends.
 */
data class ChatHomeState(
    val question: String = "",
    val messages: List<ChatMessage> = emptyList(),
    val phase: SubmissionPhase = SubmissionPhase.IDLE,
    val submittedQuestion: String? = null,
    val lastResponseStatus: AnswerStatus? = null,
    val landIdsToChoose: List<String> = emptyList(),
    val failure: RequestFailure? = null,
    val failedQuestion: String? = null,
) {
    val canAsk: Boolean
        get() = phase == SubmissionPhase.IDLE &&
            question.isNotBlank() &&
            question.length <= MAX_QUESTION_LENGTH

    val isOverCharacterLimit: Boolean get() = question.length > MAX_QUESTION_LENGTH

    /**
     * True while the last response asks the person to choose a land. The land choice
     * itself belongs to the land-clarification feature; this slice keeps the status and
     * the opaque ids without inventing a choice.
     */
    val awaitingLandClarification: Boolean
        get() = phase == SubmissionPhase.IDLE &&
            lastResponseStatus == AnswerStatus.needs_land_clarification
}

enum class SubmissionPhase { IDLE, SUBMITTING }

/**
 * One transcript entry. [answerStatus] and [sources] are meaningful only for [Speaker.ASSISTANT]
 * entries and are copied from the decoded [AskResponse] at the single creation site
 * ([ChatHomeAction.ResponseReceived]); neither is ever read for a [Speaker.USER] entry and neither is
 * ever inferred from [ChatHomeState.lastResponseStatus], so every entry keeps the payload it arrived
 * with. The defaults keep existing user entries compiling; a future assistant-entry creation site
 * must set both from the decoded response.
 */
data class ChatMessage(
    val speaker: Speaker,
    val text: String,
    val answerStatus: AnswerStatus = AnswerStatus.answered,
    /** The `sources` the response arrived with, in payload order. Never read for [Speaker.USER]. */
    val sources: List<AnswerSource> = emptyList(),
)

enum class Speaker { USER, ASSISTANT }

sealed interface ChatHomeAction {
    data class QuestionChanged(val value: String) : ChatHomeAction
    data class SuggestedQuestionSelected(val question: String) : ChatHomeAction
    data object AskClicked : ChatHomeAction
    data class ResponseReceived(val response: AskResponse) : ChatHomeAction
    data class RequestFailed(val failure: RequestFailure) : ChatHomeAction
    data object RetryClicked : ChatHomeAction
}

sealed interface ChatEffect {
    data class Submit(val question: String) : ChatEffect
}

data class ChatReduction(val state: ChatHomeState, val effect: ChatEffect? = null)

/**
 * Pure state machine. It refuses to submit blank or over-limit questions and while a
 * request is already in flight, and it keeps the submitted wording immutable so the user
 * message and the request always carry the original text.
 *
 * A failure is stored as state ([ChatHomeState.failure]) and never as a transcript entry. A
 * draft typed during the request is preserved; otherwise the composer regains the failed wording,
 * and [ChatHomeAction.RetryClicked] resends that exact wording without adding a second user
 * message.
 */
fun ChatHomeState.reduce(action: ChatHomeAction): ChatReduction = when (action) {
    is ChatHomeAction.QuestionChanged ->
        ChatReduction(
            copy(
                question = action.value,
                submittedQuestion = null,
                failure = null,
                failedQuestion = null,
            ),
        )

    is ChatHomeAction.SuggestedQuestionSelected ->
        ChatReduction(
            copy(
                question = action.question,
                submittedQuestion = null,
                failure = null,
                failedQuestion = null,
            ),
        )

    ChatHomeAction.AskClicked -> {
        if (!canAsk) ChatReduction(this) else {
            val originalQuestion = question
            ChatReduction(
                state = copy(
                    question = "",
                    messages = messages + ChatMessage(Speaker.USER, originalQuestion),
                    phase = SubmissionPhase.SUBMITTING,
                    submittedQuestion = originalQuestion,
                    lastResponseStatus = null,
                    landIdsToChoose = emptyList(),
                    failure = null,
                    failedQuestion = null,
                ),
                effect = ChatEffect.Submit(originalQuestion),
            )
        }
    }

    is ChatHomeAction.ResponseReceived -> {
        if (phase != SubmissionPhase.SUBMITTING) ChatReduction(this) else {
            val response = action.response
            val assistantMessage = response.answer.takeIf { it.isNotEmpty() }
                ?.let { ChatMessage(Speaker.ASSISTANT, it, response.status, response.sources) }
            ChatReduction(
                copy(
                    messages = if (assistantMessage == null) messages else messages + assistantMessage,
                    phase = SubmissionPhase.IDLE,
                    submittedQuestion = null,
                    lastResponseStatus = response.status,
                    landIdsToChoose = response.land_ids_to_choose,
                    failure = null,
                    failedQuestion = null,
                ),
            )
        }
    }

    is ChatHomeAction.RequestFailed -> {
        if (phase != SubmissionPhase.SUBMITTING) ChatReduction(this) else {
            // The wording that was actually sent for this request. It is normally
            // `submittedQuestion`, but a draft typed during the request clears that field, and the
            // appended user message is then the record of what the person asked: a failure is
            // always retryable with the exact original wording.
            val wording = submittedQuestion ?: messages.lastOrNull { it.speaker == Speaker.USER }?.text
            ChatReduction(
                copy(
                    // Keep the original wording available without discarding a new draft.
                    question = question.ifBlank { wording.orEmpty() },
                    phase = SubmissionPhase.IDLE,
                    submittedQuestion = null,
                    failure = action.failure,
                    failedQuestion = wording,
                ),
            )
        }
    }

    ChatHomeAction.RetryClicked -> {
        val wording = failedQuestion
        if (phase != SubmissionPhase.IDLE || failure == null || wording == null) {
            // Not actionable without a retained failure, and never actionable while submitting.
            ChatReduction(this)
        } else {
            ChatReduction(
                state = copy(
                    question = "",
                    phase = SubmissionPhase.SUBMITTING,
                    submittedQuestion = wording,
                    // messages stay untouched: a retry never appends a second user message.
                    failure = null,
                ),
                effect = ChatEffect.Submit(wording),
            )
        }
    }
}

fun ChatEffect.request() = when (this) {
    is ChatEffect.Submit -> generalAskRequest(question)
}
