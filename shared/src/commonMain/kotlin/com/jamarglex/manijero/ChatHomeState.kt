package com.jamarglex.manijero

import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.MAX_QUESTION_LENGTH
import com.jamarglex.manijero.chat.generalAskRequest

/**
 * Presentation state for one chat home screen. It is intentionally pure data: the only
 * way to advance it is [reduce], which also declares the work the caller has to run.
 */
data class ChatHomeState(
    val question: String = "",
    val messages: List<ChatMessage> = emptyList(),
    val phase: SubmissionPhase = SubmissionPhase.IDLE,
    val submittedQuestion: String? = null,
    val lastResponseStatus: AnswerStatus? = null,
    val landIdsToChoose: List<String> = emptyList(),
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

data class ChatMessage(val speaker: Speaker, val text: String)

enum class Speaker { USER, ASSISTANT }

sealed interface ChatHomeAction {
    data class QuestionChanged(val value: String) : ChatHomeAction
    data object AskClicked : ChatHomeAction
    data class ResponseReceived(val response: AskResponse) : ChatHomeAction
    data object RequestFailed : ChatHomeAction
}

sealed interface ChatEffect {
    data class Submit(val question: String) : ChatEffect
}

data class ChatReduction(val state: ChatHomeState, val effect: ChatEffect? = null)

/**
 * Pure state machine. It refuses to submit blank or over-limit questions and while a
 * request is already in flight, and it keeps the submitted wording immutable so the user
 * message and the request always carry the original text.
 */
fun ChatHomeState.reduce(action: ChatHomeAction): ChatReduction = when (action) {
    is ChatHomeAction.QuestionChanged -> ChatReduction(copy(question = action.value))

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
                ),
                effect = ChatEffect.Submit(originalQuestion),
            )
        }
    }

    is ChatHomeAction.ResponseReceived -> {
        if (phase != SubmissionPhase.SUBMITTING) ChatReduction(this) else {
            val response = action.response
            val assistantMessage = response.answer.takeIf { it.isNotEmpty() }
                ?.let { ChatMessage(Speaker.ASSISTANT, it) }
            ChatReduction(
                copy(
                    messages = if (assistantMessage == null) messages else messages + assistantMessage,
                    phase = SubmissionPhase.IDLE,
                    submittedQuestion = null,
                    lastResponseStatus = response.status,
                    landIdsToChoose = response.land_ids_to_choose,
                ),
            )
        }
    }

    ChatHomeAction.RequestFailed -> {
        if (phase != SubmissionPhase.SUBMITTING) ChatReduction(this) else {
            ChatReduction(
                copy(
                    // Keep the original wording available without discarding a new draft.
                    question = question.ifBlank { submittedQuestion.orEmpty() },
                    phase = SubmissionPhase.IDLE,
                    submittedQuestion = null,
                ),
            )
        }
    }
}

fun ChatEffect.request() = when (this) {
    is ChatEffect.Submit -> generalAskRequest(question)
}
