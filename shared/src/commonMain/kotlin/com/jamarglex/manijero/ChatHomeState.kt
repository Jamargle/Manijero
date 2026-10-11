package com.jamarglex.manijero

data class ChatHomeState(
    val question: String = "",
    val submittedQuestion: String? = null,
) {
    val canAsk: Boolean
        get() = question.isNotBlank()
}

sealed interface ChatHomeAction {
    data class QuestionChanged(val value: String) : ChatHomeAction
    data object AskClicked : ChatHomeAction
}

fun ChatHomeState.reduce(action: ChatHomeAction): ChatHomeState = when (action) {
    is ChatHomeAction.QuestionChanged -> copy(question = action.value, submittedQuestion = null)
    ChatHomeAction.AskClicked -> if (canAsk) copy(submittedQuestion = question) else this
}
