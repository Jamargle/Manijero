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
}
