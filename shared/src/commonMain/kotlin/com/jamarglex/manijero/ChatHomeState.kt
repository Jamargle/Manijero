package com.jamarglex.manijero

import com.jamarglex.manijero.chat.AnswerSource
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.MAX_QUESTION_LENGTH
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.chat.askRequestFor
import com.jamarglex.manijero.chat.generalAskRequest
import com.jamarglex.manijero.chat.selectedAskRequest
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.privacy.retentionAllowedFor

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
    val clarificationQuestion: String? = null,
    /**
     * The person's explicit permission to keep the **next** sent question and its answer for
     * product improvement. Unchecked by default, never set by sending, and reset to `false` by every
     * send (ask, retry, or land choice), so each retained question needs its own fresh choice.
     */
    val retainNextQuestion: Boolean = false,
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
 * One transcript entry. [answerStatus], [sources], and [landScope] are meaningful only for
 * [Speaker.ASSISTANT] entries and are copied from the decoded [AskResponse] at the single creation
 * site ([ChatHomeAction.ResponseReceived]); none is ever read for a [Speaker.USER] entry and none is
 * ever inferred from [ChatHomeState.lastResponseStatus], so every entry keeps the payload it arrived
 * with. The defaults keep existing user entries compiling; a future assistant-entry creation site
 * must set all three from the decoded response.
 */
data class ChatMessage(
    val speaker: Speaker,
    val text: String,
    val answerStatus: AnswerStatus = AnswerStatus.answered,
    /** The `sources` the response arrived with, in payload order. Never read for [Speaker.USER]. */
    val sources: List<AnswerSource> = emptyList(),
    /**
     * Assistant-only: the `land_scope` the response arrived with. Never read for [Speaker.USER]. The
     * default is the safe `general`: a future creation site that forgets the field shows "not using
     * lands" rather than implying land context.
     */
    val landScope: LandContextMode = LandContextMode.general,
)

enum class Speaker { USER, ASSISTANT }

sealed interface ChatHomeAction {
    data class QuestionChanged(val value: String) : ChatHomeAction
    data class SuggestedQuestionSelected(val question: String) : ChatHomeAction
    data object AskClicked : ChatHomeAction
    data class ResponseReceived(val response: AskResponse) : ChatHomeAction
    data class RequestFailed(val failure: RequestFailure) : ChatHomeAction
    data object RetryClicked : ChatHomeAction

    /** The person ticked or unticked the retention box. It never submits anything. */
    data class RetentionChoiceChanged(val allowed: Boolean) : ChatHomeAction

    /**
     * The person chose one or more of the lands offered by a clarification. The original question is
     * resubmitted with `mode: selected` and no second user message (exactly the [RetryClicked]
     * pattern).
     */
    data class LandChoiceSubmitted(val selectedLandIds: List<String>) : ChatHomeAction
}

sealed interface ChatEffect {
    /** The exact wording to send. */
    val question: String

    /** Whether the person explicitly allowed retention for this one send. */
    val retainForImprovement: Boolean

    data class Submit(
        override val question: String,
        override val retainForImprovement: Boolean = false,
    ) : ChatEffect

    /** The chosen lands to resubmit the retained question over, without a second user message. */
    data class SubmitSelected(
        override val question: String,
        val landIds: List<String>,
        override val retainForImprovement: Boolean = false,
    ) : ChatEffect
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

    is ChatHomeAction.RetentionChoiceChanged ->
        ChatReduction(copy(retainNextQuestion = action.allowed))

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
                    // A fresh question is not a clarification: drop any retained wording.
                    clarificationQuestion = null,
                    // The permission covered this one question only.
                    retainNextQuestion = false,
                ),
                effect = ChatEffect.Submit(originalQuestion, retainNextQuestion),
            )
        }
    }

    is ChatHomeAction.ResponseReceived -> {
        if (phase != SubmissionPhase.SUBMITTING) ChatReduction(this) else {
            val response = action.response
            val assistantMessage = response.answer.takeIf { it.isNotEmpty() }
                ?.let {
                    ChatMessage(
                        Speaker.ASSISTANT,
                        it,
                        response.status,
                        response.sources,
                        response.land_scope,
                    )
                }
            ChatReduction(
                copy(
                    messages = if (assistantMessage == null) messages else messages + assistantMessage,
                    phase = SubmissionPhase.IDLE,
                    submittedQuestion = null,
                    lastResponseStatus = response.status,
                    landIdsToChoose = response.land_ids_to_choose,
                    failure = null,
                    failedQuestion = null,
                    // The clarification response has an empty answer, so `submittedQuestion` is about
                    // to be cleared: retain the exact original wording for the land choice here.
                    clarificationQuestion = submittedQuestion
                        .takeIf { response.status == AnswerStatus.needs_land_clarification },
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
                    retainNextQuestion = false,
                ),
                effect = ChatEffect.Submit(wording, retainNextQuestion),
            )
        }
    }

    is ChatHomeAction.LandChoiceSubmitted -> {
        val wording = clarificationQuestion
        // Actionable only while a clarification is pending, idle, with a retained question and at
        // least one chosen land. messages stay untouched: a choice never appends a second user
        // message, reusing the exact original wording.
        if (phase != SubmissionPhase.IDLE ||
            !awaitingLandClarification ||
            wording == null ||
            action.selectedLandIds.isEmpty()
        ) {
            ChatReduction(this)
        } else {
            ChatReduction(
                state = copy(
                    question = "",
                    phase = SubmissionPhase.SUBMITTING,
                    submittedQuestion = wording,
                    failure = null,
                    failedQuestion = null,
                    retainNextQuestion = false,
                    // messages untouched, exactly like RetryClicked.
                ),
                effect = ChatEffect.SubmitSelected(wording, action.selectedLandIds, retainNextQuestion),
            )
        }
    }
}

/**
 * Maps one submission effect to the request to send. The lands are passed in explicitly rather than
 * read here, so the reducer stays pure and a call site cannot forget the current land list: the
 * caller supplies the list it just read (see `ChatConversation.submit`).
 *
 * [ChatEffect.SubmitSelected] keeps only the chosen ids that still exist in the freshly read list
 * (repository order), ignoring a returned id that is not stored locally; if none remain, it degrades
 * to the accepted `general` request instead of inventing or resending a removed land.
 */
fun ChatEffect.request(lands: List<Land>) = when (this) {
    is ChatEffect.Submit -> askRequestFor(question, lands)
    is ChatEffect.SubmitSelected -> {
        val chosen = lands.filter { land -> land.id in landIds }
        if (chosen.isEmpty()) generalAskRequest(question) else selectedAskRequest(question, chosen)
    }
}.let { request ->
    // Retention is requested only with the person's explicit choice for this send, and never when
    // the wording contains a saved land's private label (see `retentionAllowedFor`).
    if (retainForImprovement && retentionAllowedFor(question, lands)) {
        request.copy(retain_for_improvement = true)
    } else {
        request
    }
}
