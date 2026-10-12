package com.jamarglex.manijero

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ChatHomeStateTest {
    @Test
    fun `blank question cannot be submitted`() {
        val state = ChatHomeState(question = " \n\t")

        assertFalse(state.canAsk)
        assertEquals(null, state.reduce(ChatHomeAction.AskClicked).submittedQuestion)
    }

    @Test
    fun `submitted question preserves original wording`() {
        val question = "  ¿Puedo regar hoy?  "
        val state = ChatHomeState().reduce(ChatHomeAction.QuestionChanged(question))

        assertTrue(state.canAsk)
        assertEquals(question, state.reduce(ChatHomeAction.AskClicked).submittedQuestion)
    }

    @Test
    fun `editing after submit clears stale submitted state`() {
        val state = ChatHomeState(question = "¿Qué puedo hacer?")
            .reduce(ChatHomeAction.AskClicked)
            .reduce(ChatHomeAction.QuestionChanged("😀 ¿Y ahora?"))

        assertEquals("😀 ¿Y ahora?", state.question)
        assertEquals(null, state.submittedQuestion)
    }

    @Test
    fun `selecting an example replaces the current question text`() {
        val example = "¿Qué es el SIGPAC y para qué sirve?"
        val state = ChatHomeState(question = "escribe otra cosa")
            .reduce(ChatHomeAction.SuggestedQuestionSelected(example))

        assertEquals(example, state.question)
        assertTrue(state.canAsk)
    }

    @Test
    fun `selecting an example clears stale submitted state`() {
        val example = "¿Qué obligaciones tengo por la condicionalidad?"
        val state = ChatHomeState(question = "¿Puedo regar hoy?")
            .reduce(ChatHomeAction.AskClicked)
            .reduce(ChatHomeAction.SuggestedQuestionSelected(example))

        assertEquals(example, state.question)
        assertEquals(null, state.submittedQuestion)
    }

    @Test
    fun `selected example submits verbatim and keeps later edits`() {
        val example = "¿Qué necesito preparar para la solicitud única?"
        val selected = ChatHomeState().reduce(ChatHomeAction.SuggestedQuestionSelected(example))

        assertEquals(example, selected.reduce(ChatHomeAction.AskClicked).submittedQuestion)

        val edited = selected.reduce(ChatHomeAction.QuestionChanged("$example En mi olivar."))
        assertEquals("$example En mi olivar.", edited.question)
        assertEquals("$example En mi olivar.", edited.reduce(ChatHomeAction.AskClicked).submittedQuestion)
    }

    @Test
    fun `selection keeps Spanish punctuation and Unicode intact`() {
        val example = "¿Qué necesito preparar para la solicitud única?"
        val state = ChatHomeState().reduce(ChatHomeAction.SuggestedQuestionSelected(example))

        assertEquals("¿Qué necesito preparar para la solicitud única?", state.question)
        assertEquals(null, state.submittedQuestion)
    }
}
