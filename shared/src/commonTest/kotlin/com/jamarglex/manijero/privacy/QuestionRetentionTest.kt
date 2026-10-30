package com.jamarglex.manijero.privacy

import com.jamarglex.manijero.ChatEffect
import com.jamarglex.manijero.ChatHomeAction
import com.jamarglex.manijero.ChatHomeState
import com.jamarglex.manijero.SubmissionPhase
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskRequest
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.chat.answerJson
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.reduce
import com.jamarglex.manijero.request
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * The per-question retention permission: off by default, explicit, separate from sending, reset by
 * every send, encoded only when given, and dropped when the wording carries a saved land's label.
 */
class QuestionRetentionTest {
    private val question = "¿Cuándo se presenta la solicitud única?"
    private val land = Land(
        id = "land-1",
        name = "Los Olivos",
        zone = "Linde del arroyo",
        municipality = "Martos",
        notes = "Nota privada",
        createdAtEpochMillis = 1L,
        updatedAtEpochMillis = 1L,
    )

    private fun encode(request: AskRequest) = answerJson.encodeToString(AskRequest.serializer(), request)

    @Test
    fun `retention is off by default and the request carries no retention key`() {
        val state = ChatHomeState(question = question)
        assertFalse(state.retainNextQuestion)

        val effect = state.reduce(ChatHomeAction.AskClicked).effect as ChatEffect.Submit
        assertFalse(effect.retainForImprovement)
        val encoded = encode(effect.request(emptyList()))
        assertFalse(encoded.contains("retain_for_improvement"), encoded)
    }

    @Test
    fun `ticking the box never sends and only changes the choice`() {
        val state = ChatHomeState(question = question)
        val reduction = state.reduce(ChatHomeAction.RetentionChoiceChanged(true))

        assertEquals(null, reduction.effect)
        assertEquals(state.copy(retainNextQuestion = true), reduction.state)
        assertFalse(reduction.state.reduce(ChatHomeAction.RetentionChoiceChanged(false)).state.retainNextQuestion)
    }

    @Test
    fun `an explicit choice applies to one question and is then reset`() {
        val opted = ChatHomeState(question = question)
            .reduce(ChatHomeAction.RetentionChoiceChanged(true)).state
        val sent = opted.reduce(ChatHomeAction.AskClicked)

        val effect = sent.effect as ChatEffect.Submit
        assertTrue(effect.retainForImprovement)
        assertFalse(sent.state.retainNextQuestion, "the next question needs a fresh choice")
        assertTrue(encode(effect.request(emptyList())).contains("\"retain_for_improvement\":true"))

        val next = sent.state
            .reduce(
                ChatHomeAction.ResponseReceived(
                    AskResponse(AnswerStatus.answered, "Respuesta.", emptyList(), LandContextMode.general, emptyList()),
                ),
            ).state
            .reduce(ChatHomeAction.QuestionChanged("Otra pregunta"))
            .state
            .reduce(ChatHomeAction.AskClicked)
        assertFalse((next.effect as ChatEffect.Submit).retainForImprovement)
    }

    @Test
    fun `a retry or a land choice uses only a fresh choice`() {
        val failed = ChatHomeState(
            failure = RequestFailure.SERVICE_ERROR,
            failedQuestion = question,
            phase = SubmissionPhase.IDLE,
        )
        assertFalse((failed.reduce(ChatHomeAction.RetryClicked).effect as ChatEffect.Submit).retainForImprovement)
        val retried = failed.copy(retainNextQuestion = true).reduce(ChatHomeAction.RetryClicked)
        assertTrue((retried.effect as ChatEffect.Submit).retainForImprovement)
        assertFalse(retried.state.retainNextQuestion)

        val clarifying = ChatHomeState(
            lastResponseStatus = AnswerStatus.needs_land_clarification,
            clarificationQuestion = question,
            landIdsToChoose = listOf("land-1"),
            retainNextQuestion = true,
        )
        val chosen = clarifying.reduce(ChatHomeAction.LandChoiceSubmitted(listOf("land-1")))
        val effect = chosen.effect as ChatEffect.SubmitSelected
        assertTrue(effect.retainForImprovement)
        assertFalse(chosen.state.retainNextQuestion)
        assertTrue(effect.request(listOf(land)).retain_for_improvement)
    }

    @Test
    fun `a question that names a saved land is never sent for retention`() {
        listOf(
            "¿Puedo regar Los Olivos?",
            "¿Qué hago en el linde del arroyo?",
            "¿Hay ayudas en MARTOS?",
            "Mi nota privada dice algo",
        ).forEach { wording ->
            assertFalse(retentionAllowedFor(wording, listOf(land)), wording)
            val request = ChatEffect.Submit(wording, retainForImprovement = true).request(listOf(land))
            assertFalse(request.retain_for_improvement, wording)
            assertEquals(wording, request.question, "the wording is never changed")
        }
        assertTrue(retentionAllowedFor(question, listOf(land)))
        assertTrue(ChatEffect.Submit(question, retainForImprovement = true).request(listOf(land)).retain_for_improvement)
    }

    @Test
    fun `the retained question never carries extra land data in the payload`() {
        val encoded = encode(ChatEffect.Submit(question, retainForImprovement = true).request(listOf(land)))

        listOf("Los Olivos", "Linde del arroyo", "Nota privada", "notes", "name").forEach { forbidden ->
            assertFalse(encoded.contains(forbidden), forbidden)
        }
    }

    @Test
    fun `the copy and the service share the thirty day limit`() {
        assertEquals(30, RETENTION_MAX_DAYS)
    }
}
