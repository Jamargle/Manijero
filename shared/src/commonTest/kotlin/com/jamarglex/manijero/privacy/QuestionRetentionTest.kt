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
 * The standing `Ayúdanos a mejorar` permission: off by default, explicit, separate from sending,
 * kept across sends until turned off, encoded only while on, and dropped when the wording carries a
 * saved land's label.
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
        assertFalse(state.retainQuestions)

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
        assertEquals(state.copy(retainQuestions = true), reduction.state)
        assertFalse(reduction.state.reduce(ChatHomeAction.RetentionChoiceChanged(false)).state.retainQuestions)
    }

    @Test
    fun `the choice stays on across questions until it is turned off`() {
        val opted = ChatHomeState(question = question)
            .reduce(ChatHomeAction.RetentionChoiceChanged(true)).state
        val sent = opted.reduce(ChatHomeAction.AskClicked)

        val effect = sent.effect as ChatEffect.Submit
        assertTrue(effect.retainForImprovement)
        assertTrue(sent.state.retainQuestions, "the choice is standing, not per question")
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
        assertTrue((next.effect as ChatEffect.Submit).retainForImprovement)

        val off = next.state
            .reduce(
                ChatHomeAction.ResponseReceived(
                    AskResponse(AnswerStatus.answered, "Respuesta.", emptyList(), LandContextMode.general, emptyList()),
                ),
            ).state
            .reduce(ChatHomeAction.RetentionChoiceChanged(false)).state
            .reduce(ChatHomeAction.QuestionChanged("Tercera pregunta")).state
            .reduce(ChatHomeAction.AskClicked)
        assertFalse((off.effect as ChatEffect.Submit).retainForImprovement)
    }

    @Test
    fun `a retry or a land choice uses the current choice and keeps it`() {
        val failed = ChatHomeState(
            failure = RequestFailure.SERVICE_ERROR,
            failedQuestion = question,
            phase = SubmissionPhase.IDLE,
        )
        assertFalse((failed.reduce(ChatHomeAction.RetryClicked).effect as ChatEffect.Submit).retainForImprovement)
        val retried = failed.copy(retainQuestions = true).reduce(ChatHomeAction.RetryClicked)
        assertTrue((retried.effect as ChatEffect.Submit).retainForImprovement)
        assertTrue(retried.state.retainQuestions)

        val clarifying = ChatHomeState(
            lastResponseStatus = AnswerStatus.needs_land_clarification,
            clarificationQuestion = question,
            landIdsToChoose = listOf("land-1"),
            retainQuestions = true,
        )
        val chosen = clarifying.reduce(ChatHomeAction.LandChoiceSubmitted(listOf("land-1")))
        val effect = chosen.effect as ChatEffect.SubmitSelected
        assertTrue(effect.retainForImprovement)
        assertTrue(chosen.state.retainQuestions)
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
