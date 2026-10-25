package com.jamarglex.manijero

import com.jamarglex.manijero.chat.AnswerSource
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.MAX_QUESTION_LENGTH
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.lands.WaterRegime as LocalWaterRegime
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ChatHomeStateTest {
    private val originalQuestion = "  ¿Puedo regar hoy?  "

    private fun response(
        status: AnswerStatus = AnswerStatus.answered,
        answer: String = "Una respuesta.",
        landIds: List<String> = emptyList(),
        sources: List<AnswerSource> = emptyList(),
        landScope: LandContextMode = LandContextMode.general,
    ) = AskResponse(
        status = status,
        answer = answer,
        sources = sources,
        land_scope = landScope,
        land_ids_to_choose = landIds,
    )

    private fun source(title: String = "Solicitud única de la PAC") = AnswerSource(
        title = title,
        issuing_body = "Ministerio de Agricultura, Pesca y Alimentación",
        url = "https://www.mapa.gob.es/",
        location = "Información de la solicitud única",
        published_or_updated_on = "2026-01-15",
        verified_on = "2026-10-01",
        excerpt = "La solicitud única es el procedimiento anual para solicitar determinadas ayudas de la PAC.",
    )

    private fun typed(question: String) =
        ChatHomeState().reduce(ChatHomeAction.QuestionChanged(question)).state

    private fun submitting(question: String = originalQuestion) =
        typed(question).reduce(ChatHomeAction.AskClicked).state

    private fun failed(
        failure: RequestFailure = RequestFailure.SERVICE_ERROR,
        question: String = originalQuestion,
    ) = submitting(question).reduce(ChatHomeAction.RequestFailed(failure)).state

    @Test
    fun `blank question cannot be submitted`() {
        val state = typed(" \n\t")

        assertFalse(state.canAsk)
        val reduction = state.reduce(ChatHomeAction.AskClicked)
        assertNull(reduction.effect)
        assertTrue(reduction.state.messages.isEmpty())
        assertEquals(SubmissionPhase.IDLE, reduction.state.phase)
    }

    @Test
    fun `question over the contract limit cannot be submitted`() {
        val state = typed("a".repeat(MAX_QUESTION_LENGTH + 1))

        assertTrue(state.isOverCharacterLimit)
        assertFalse(state.canAsk)
        assertNull(state.reduce(ChatHomeAction.AskClicked).effect)
    }

    @Test
    fun `question at the contract limit can be submitted`() {
        val state = typed("a".repeat(MAX_QUESTION_LENGTH))

        assertFalse(state.isOverCharacterLimit)
        assertTrue(state.canAsk)
    }

    @Test
    fun `accepted question keeps exact wording and asks nothing else`() {
        val reduction = typed(originalQuestion).reduce(ChatHomeAction.AskClicked)

        assertEquals(originalQuestion, reduction.state.messages.single().text)
        assertEquals(Speaker.USER, reduction.state.messages.single().speaker)
        assertEquals("", reduction.state.question)
        assertEquals(SubmissionPhase.SUBMITTING, reduction.state.phase)

        val effect = reduction.effect as ChatEffect.Submit
        assertEquals(originalQuestion, effect.question)
        val request = effect.request(emptyList())
        assertEquals(originalQuestion, request.question)
        assertEquals(LandContextMode.general, request.land_context.mode)
        assertTrue(request.land_context.lands.isEmpty())
    }

    @Test
    fun `a question is only sent once while the request is in flight`() {
        val inFlight = submitting()

        assertFalse(inFlight.canAsk)
        val duplicate = inFlight.reduce(ChatHomeAction.AskClicked)
        assertNull(duplicate.effect)
        assertEquals(1, duplicate.state.messages.size)
        assertEquals(SubmissionPhase.SUBMITTING, duplicate.state.phase)
    }

    @Test
    fun `a response becomes exactly one assistant message`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(response(answer = "Respuesta del servicio.")),
        ).state

        assertEquals(2, state.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), state.messages[0])
        assertEquals(ChatMessage(Speaker.ASSISTANT, "Respuesta del servicio."), state.messages[1])
        assertEquals(1, state.messages.count { it.speaker == Speaker.ASSISTANT })
        assertEquals(SubmissionPhase.IDLE, state.phase)
        assertNull(state.submittedQuestion)
    }

    @Test
    fun `a repeated response is not appended twice`() {
        val idle = submitting().reduce(
            ChatHomeAction.ResponseReceived(response(answer = "Primera.")),
        ).state

        val repeated = idle.reduce(ChatHomeAction.ResponseReceived(response(answer = "Segunda.")))

        assertEquals(1, repeated.state.messages.count { it.speaker == Speaker.ASSISTANT })
        assertEquals("Primera.", repeated.state.messages.last().text)
    }

    @Test
    fun `a later question can be submitted after a reply`() {
        val idle = submitting().reduce(
            ChatHomeAction.ResponseReceived(response()),
        ).state

        val next = idle.reduce(ChatHomeAction.QuestionChanged("¿Y ahora?"))

        assertTrue(next.state.canAsk)
        assertEquals(2, next.state.messages.size)
    }

    @Test
    fun `abstained answer is retained once without becoming a clarification`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(status = AnswerStatus.abstained, answer = "No puedo confirmarlo."),
            ),
        ).state

        assertEquals(AnswerStatus.abstained, state.lastResponseStatus)
        assertEquals("No puedo confirmarlo.", state.messages.last().text)
        assertFalse(state.awaitingLandClarification)
    }

    @Test
    fun `an answered response marks its assistant entry as answered`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(response(answer = "Respuesta del servicio.")),
        ).state

        val assistant = state.messages.single { it.speaker == Speaker.ASSISTANT }
        assertEquals(AnswerStatus.answered, assistant.answerStatus)
        assertEquals("Respuesta del servicio.", assistant.text)
    }

    @Test
    fun `an abstained response marks its entry as abstained and keeps the message verbatim`() {
        val pinned = "No he encontrado esta información en los documentos oficiales que tengo. " +
            "Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(status = AnswerStatus.abstained, answer = pinned),
            ),
        ).state

        val assistant = state.messages.single { it.speaker == Speaker.ASSISTANT }
        assertEquals(AnswerStatus.abstained, assistant.answerStatus)
        assertEquals(pinned, assistant.text)
    }

    @Test
    fun `an earlier abstention keeps its state after a later answered reply`() {
        val abstained = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(status = AnswerStatus.abstained, answer = "No puedo confirmarlo."),
            ),
        ).state

        val nextTurn = abstained
            .reduce(ChatHomeAction.QuestionChanged("¿Y esto?"))
            .state
            .reduce(ChatHomeAction.AskClicked)
            .state
            .reduce(ChatHomeAction.ResponseReceived(response(answer = "Ahora sí.")))
            .state

        assertEquals(4, nextTurn.messages.size)
        // The earlier abstention stays caution-marked; only the latest turn reaches lastResponseStatus.
        assertEquals(AnswerStatus.abstained, nextTurn.messages[1].answerStatus)
        assertEquals(AnswerStatus.answered, nextTurn.messages[3].answerStatus)
        assertEquals(AnswerStatus.answered, nextTurn.lastResponseStatus)
    }

    @Test
    fun `an answered response carries its decoded sources in payload order`() {
        val sources = listOf(source(title = "Primera fuente"), source(title = "Segunda fuente"))
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(answer = "La primera. [1] La segunda. [2]", sources = sources),
            ),
        ).state

        val assistant = state.messages.single { it.speaker == Speaker.ASSISTANT }
        assertEquals(sources, assistant.sources)
        assertEquals(listOf("Primera fuente", "Segunda fuente"), assistant.sources.map { it.title })
        assertTrue(state.messages.single { it.speaker == Speaker.USER }.sources.isEmpty())
    }

    @Test
    fun `a later turn does not change an earlier entry's sources`() {
        val firstSources = listOf(source(title = "Primera fuente"))
        val answered = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(answer = "La primera. [1]", sources = firstSources),
            ),
        ).state

        val nextTurn = answered
            .reduce(ChatHomeAction.QuestionChanged("¿Y esto?"))
            .state
            .reduce(ChatHomeAction.AskClicked)
            .state
            .reduce(ChatHomeAction.ResponseReceived(response(answer = "Otra respuesta.")))
            .state

        assertEquals(4, nextTurn.messages.size)
        // The earlier entry keeps exactly its own sources; the latest turn carries none.
        assertEquals(firstSources, nextTurn.messages[1].sources)
        assertTrue(nextTurn.messages[3].sources.isEmpty())
    }

    @Test
    fun `an abstained entry carries no sources`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(status = AnswerStatus.abstained, answer = "No puedo confirmarlo."),
            ),
        ).state

        val assistant = state.messages.single { it.speaker == Speaker.ASSISTANT }
        assertTrue(assistant.sources.isEmpty())
    }

    @Test
    fun `an assistant entry defaults to the safe general scope`() {
        // The default is "not using lands": a future creation site that forgets the field must never
        // imply land context.
        assertEquals(LandContextMode.general, ChatMessage(Speaker.ASSISTANT, "texto").landScope)
    }

    @Test
    fun `each decoded land scope is copied onto the assistant entry`() {
        val scopes = listOf(
            LandContextMode.general,
            LandContextMode.all_active,
            LandContextMode.selected,
        )

        scopes.forEach { scope ->
            val state = submitting().reduce(
                ChatHomeAction.ResponseReceived(response(answer = "Respuesta.", landScope = scope)),
            ).state

            assertEquals(1, state.messages.count { it.speaker == Speaker.ASSISTANT })
            val assistant = state.messages.single { it.speaker == Speaker.ASSISTANT }
            assertEquals(scope, assistant.landScope)
            assertEquals("Respuesta.", assistant.text)
        }
    }

    @Test
    fun `a user entry never carries an assistant land scope`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(response(landScope = LandContextMode.selected)),
        ).state

        val user = state.messages.single { it.speaker == Speaker.USER }
        assertEquals(LandContextMode.general, user.landScope)
    }

    @Test
    fun `an earlier entry keeps its own scope after a later reply`() {
        val selected = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(answer = "Para el elegido.", landScope = LandContextMode.selected),
            ),
        ).state

        val nextTurn = selected
            .reduce(ChatHomeAction.QuestionChanged("¿Y esto?"))
            .state
            .reduce(ChatHomeAction.AskClicked)
            .state
            .reduce(
                ChatHomeAction.ResponseReceived(
                    response(answer = "General.", landScope = LandContextMode.general),
                ),
            )
            .state

        assertEquals(4, nextTurn.messages.size)
        // Each entry keeps the scope its own response carried, not the latest turn's scope.
        assertEquals(LandContextMode.selected, nextTurn.messages[1].landScope)
        assertEquals(LandContextMode.general, nextTurn.messages[3].landScope)
    }

    @Test
    fun `an abstained entry carries its decoded scope`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(
                    status = AnswerStatus.abstained,
                    answer = "No puedo confirmarlo.",
                    landScope = LandContextMode.all_active,
                ),
            ),
        ).state

        val assistant = state.messages.single { it.speaker == Speaker.ASSISTANT }
        assertEquals(AnswerStatus.abstained, assistant.answerStatus)
        assertEquals(LandContextMode.all_active, assistant.landScope)
    }

    @Test
    fun `a clarification still appends no assistant entry with a scope`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(
                    status = AnswerStatus.needs_land_clarification,
                    answer = "",
                    landIds = listOf("land-1"),
                    landScope = LandContextMode.selected,
                ),
            ),
        ).state

        assertEquals(1, state.messages.size)
        assertTrue(state.messages.none { it.speaker == Speaker.ASSISTANT })
    }

    @Test
    fun `clarification keeps its ids and does not invent an answer`() {
        val state = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(
                    status = AnswerStatus.needs_land_clarification,
                    answer = "",
                    landIds = listOf("land-001", "land-002"),
                ),
            ),
        ).state

        assertEquals(AnswerStatus.needs_land_clarification, state.lastResponseStatus)
        assertEquals(listOf("land-001", "land-002"), state.landIdsToChoose)
        assertEquals(1, state.messages.size)
        assertTrue(state.messages.none { it.speaker == Speaker.ASSISTANT })
        assertTrue(state.awaitingLandClarification)
    }

    @Test
    fun `a new submission clears the previous clarification state`() {
        val clarified = submitting().reduce(
            ChatHomeAction.ResponseReceived(
                response(
                    status = AnswerStatus.needs_land_clarification,
                    answer = "",
                    landIds = listOf("land-001"),
                ),
            ),
        ).state

        val resubmitted = clarified
            .reduce(ChatHomeAction.QuestionChanged("¿Y en el otro?"))
            .state
            .reduce(ChatHomeAction.AskClicked)
            .state

        assertNull(resubmitted.lastResponseStatus)
        assertTrue(resubmitted.landIdsToChoose.isEmpty())
        assertFalse(resubmitted.awaitingLandClarification)
    }

    @Test
    fun `an unreachable service is explained without adding an answer`() {
        val state = failed(RequestFailure.COULD_NOT_REACH_SERVICE)

        assertEquals(SubmissionPhase.IDLE, state.phase)
        assertNull(state.submittedQuestion)
        assertEquals(originalQuestion, state.question)
        assertTrue(state.canAsk)
        assertEquals(1, state.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), state.messages.single())
        assertTrue(state.messages.none { it.speaker == Speaker.ASSISTANT })
        assertEquals(RequestFailure.COULD_NOT_REACH_SERVICE, state.failure)
        assertEquals(originalQuestion, state.failedQuestion)
        assertNull(state.lastResponseStatus)
    }

    @Test
    fun `a service error is explained without adding an answer`() {
        val state = failed(RequestFailure.SERVICE_ERROR)

        assertEquals(RequestFailure.SERVICE_ERROR, state.failure)
        assertEquals(originalQuestion, state.failedQuestion)
        assertEquals(originalQuestion, state.question)
        assertEquals(1, state.messages.size)
        assertTrue(state.messages.none { it.speaker == Speaker.ASSISTANT })
        assertEquals(SubmissionPhase.IDLE, state.phase)
    }

    @Test
    fun `a failure does not overwrite a newly typed question`() {
        val state = submitting()
            .reduce(ChatHomeAction.QuestionChanged("Otra pregunta"))
            .state
            .reduce(ChatHomeAction.RequestFailed(RequestFailure.COULD_NOT_REACH_SERVICE))
            .state

        assertEquals("Otra pregunta", state.question)
        assertEquals(SubmissionPhase.IDLE, state.phase)
        // The sent wording is still the retryable one, taken from the appended user message,
        // so a draft typed during the request never makes the failure un-retryable.
        assertEquals(originalQuestion, state.failedQuestion)
        assertEquals(RequestFailure.COULD_NOT_REACH_SERVICE, state.failure)
        assertEquals(
            originalQuestion,
            (state.reduce(ChatHomeAction.RetryClicked).effect as ChatEffect.Submit).question,
        )
    }

    @Test
    fun `retry resends the exact wording without appending a second user message`() {
        val retry = failed(failure = RequestFailure.COULD_NOT_REACH_SERVICE)
            .reduce(ChatHomeAction.RetryClicked)

        assertEquals(SubmissionPhase.SUBMITTING, retry.state.phase)
        assertNull(retry.state.failure)
        assertEquals("", retry.state.question)
        assertEquals(1, retry.state.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), retry.state.messages.single())
        assertEquals(originalQuestion, retry.state.submittedQuestion)
        assertEquals(originalQuestion, retry.state.failedQuestion)

        val effect = retry.effect as ChatEffect.Submit
        assertEquals(originalQuestion, effect.question)
        assertEquals(originalQuestion, effect.request(emptyList()).question)
    }

    @Test
    fun `a retry that fails again keeps one user message and can be retried`() {
        val secondFailure = failed()
            .reduce(ChatHomeAction.RetryClicked)
            .state
            .reduce(ChatHomeAction.RequestFailed(RequestFailure.COULD_NOT_REACH_SERVICE))
            .state

        assertEquals(1, secondFailure.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), secondFailure.messages.single())
        assertTrue(secondFailure.messages.none { it.speaker == Speaker.ASSISTANT })
        assertEquals(RequestFailure.COULD_NOT_REACH_SERVICE, secondFailure.failure)
        assertEquals(originalQuestion, secondFailure.failedQuestion)
        assertEquals(originalQuestion, secondFailure.question)

        val thirdAttempt = secondFailure.reduce(ChatHomeAction.RetryClicked)
        assertEquals(SubmissionPhase.SUBMITTING, thirdAttempt.state.phase)
        assertEquals(1, thirdAttempt.state.messages.size)
        assertEquals(originalQuestion, (thirdAttempt.effect as ChatEffect.Submit).question)
    }

    @Test
    fun `retry is not actionable without a failure or while submitting`() {
        val noFailure = ChatHomeState(question = originalQuestion).reduce(ChatHomeAction.RetryClicked)
        assertNull(noFailure.effect)
        assertEquals(originalQuestion, noFailure.state.question)
        assertEquals(SubmissionPhase.IDLE, noFailure.state.phase)

        val failureWithoutWording = ChatHomeState(failure = RequestFailure.SERVICE_ERROR)
        assertNull(failureWithoutWording.reduce(ChatHomeAction.RetryClicked).effect)

        val inFlight = submitting()
        val duringSubmit = inFlight.reduce(ChatHomeAction.RetryClicked)
        assertNull(duringSubmit.effect)
        assertEquals(inFlight, duringSubmit.state)

        val duringRetry = failed().reduce(ChatHomeAction.RetryClicked).state
        val secondRetryClick = duringRetry.reduce(ChatHomeAction.RetryClicked)
        assertNull(secondRetryClick.effect)
        assertEquals(duringRetry, secondRetryClick.state)
    }

    @Test
    fun `a successful retry adds exactly one answer and clears the notice`() {
        val answered = failed()
            .reduce(ChatHomeAction.RetryClicked)
            .state
            .reduce(ChatHomeAction.ResponseReceived(response(answer = "Respuesta del servicio.")))
            .state

        assertEquals(SubmissionPhase.IDLE, answered.phase)
        assertNull(answered.failure)
        assertNull(answered.failedQuestion)
        assertNull(answered.submittedQuestion)
        assertEquals(2, answered.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), answered.messages[0])
        assertEquals(ChatMessage(Speaker.ASSISTANT, "Respuesta del servicio."), answered.messages[1])
        assertEquals(1, answered.messages.count { it.speaker == Speaker.ASSISTANT })
    }

    @Test
    fun `typing again dismisses the failure and its retained wording`() {
        val state = failed().reduce(ChatHomeAction.QuestionChanged("Otra pregunta")).state

        assertNull(state.failure)
        assertNull(state.failedQuestion)
        assertEquals("Otra pregunta", state.question)
        assertTrue(state.canAsk)
    }

    @Test
    fun `selecting an example dismisses the failure`() {
        val example = "¿Qué es el SIGPAC y para qué sirve?"
        val state = failed().reduce(ChatHomeAction.SuggestedQuestionSelected(example)).state

        assertNull(state.failure)
        assertNull(state.failedQuestion)
        assertEquals(example, state.question)
    }

    @Test
    fun `a decoded abstention is never treated as a failure`() {
        val state = submitting()
            .reduce(
                ChatHomeAction.ResponseReceived(
                    response(status = AnswerStatus.abstained, answer = "No puedo confirmarlo."),
                ),
            )
            .state

        assertNull(state.failure)
        assertNull(state.failedQuestion)
        assertEquals(AnswerStatus.abstained, state.lastResponseStatus)
    }

    @Test
    fun `selecting an example replaces the current question text`() {
        val example = "¿Qué es el SIGPAC y para qué sirve?"
        val state = ChatHomeState(question = "escribe otra cosa")
            .reduce(ChatHomeAction.SuggestedQuestionSelected(example))
            .state

        assertEquals(example, state.question)
        assertTrue(state.canAsk)
    }

    @Test
    fun `selecting an example clears stale submitted state`() {
        val example = "¿Qué obligaciones tengo por la condicionalidad?"
        val state = ChatHomeState(question = "¿Puedo regar hoy?")
            .reduce(ChatHomeAction.AskClicked)
            .state
            .reduce(ChatHomeAction.SuggestedQuestionSelected(example))
            .state

        assertEquals(example, state.question)
        assertNull(state.submittedQuestion)
    }

    @Test
    fun `selected example submits verbatim and keeps later edits`() {
        val example = "¿Qué necesito preparar para la solicitud única?"
        val selected = ChatHomeState()
            .reduce(ChatHomeAction.SuggestedQuestionSelected(example))
            .state

        assertEquals(example, selected.reduce(ChatHomeAction.AskClicked).state.submittedQuestion)

        val edited = selected.reduce(ChatHomeAction.QuestionChanged("$example En mi olivar.")).state
        assertEquals("$example En mi olivar.", edited.question)
        assertEquals(
            "$example En mi olivar.",
            edited.reduce(ChatHomeAction.AskClicked).state.submittedQuestion,
        )
    }

    @Test
    fun `selection keeps Spanish punctuation and Unicode intact`() {
        val example = "¿Qué necesito preparar para la solicitud única?"
        val state = ChatHomeState()
            .reduce(ChatHomeAction.SuggestedQuestionSelected(example))
            .state

        assertEquals("¿Qué necesito preparar para la solicitud única?", state.question)
        assertNull(state.submittedQuestion)
    }

    private fun land(id: String, name: String = "Terreno", water: LocalWaterRegime = LocalWaterRegime.UNKNOWN) =
        Land(
            id = id,
            name = name,
            zone = "El Llano",
            waterRegime = water,
            createdAtEpochMillis = 1L,
            updatedAtEpochMillis = 1L,
        )

    private fun clarified(
        landIds: List<String> = listOf("land-1", "land-2"),
    ) = submitting().reduce(
        ChatHomeAction.ResponseReceived(
            response(status = AnswerStatus.needs_land_clarification, answer = "", landIds = landIds),
        ),
    ).state

    @Test
    fun `a clarification retains the exact original wording for the choice`() {
        val state = clarified()

        assertEquals(originalQuestion, state.clarificationQuestion)
        assertTrue(state.awaitingLandClarification)
        assertEquals(listOf("land-1", "land-2"), state.landIdsToChoose)
    }

    @Test
    fun `a land choice resubmits the retained wording with no second user message`() {
        val reduction = clarified().reduce(ChatHomeAction.LandChoiceSubmitted(listOf("land-1")))

        assertEquals(SubmissionPhase.SUBMITTING, reduction.state.phase)
        assertEquals("", reduction.state.question)
        assertEquals(originalQuestion, reduction.state.submittedQuestion)
        // The transcript still holds exactly the one original user message.
        assertEquals(1, reduction.state.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), reduction.state.messages.single())

        val effect = reduction.effect as ChatEffect.SubmitSelected
        assertEquals(originalQuestion, effect.question)
        assertEquals(listOf("land-1"), effect.landIds)
    }

    @Test
    fun `a land choice is not actionable without a pending clarification or a chosen land`() {
        // No clarification has been received: the action changes nothing and sends nothing.
        val duringSubmit = submitting().reduce(ChatHomeAction.LandChoiceSubmitted(listOf("land-1")))
        assertNull(duringSubmit.effect)
        assertEquals(1, duringSubmit.state.messages.size)

        // A clarification without the retained wording cannot resubmit anything.
        val noWording = ChatHomeState(
            lastResponseStatus = AnswerStatus.needs_land_clarification,
            landIdsToChoose = listOf("land-1"),
        ).reduce(ChatHomeAction.LandChoiceSubmitted(listOf("land-1")))
        assertNull(noWording.effect)

        // An empty selection never submits.
        val emptySelection = clarified().reduce(ChatHomeAction.LandChoiceSubmitted(emptyList()))
        assertNull(emptySelection.effect)
        assertEquals(SubmissionPhase.IDLE, emptySelection.state.phase)

        // A second choice while the resubmission is in flight is ignored.
        val inFlight = clarified().reduce(ChatHomeAction.LandChoiceSubmitted(listOf("land-1"))).state
        assertNull(inFlight.reduce(ChatHomeAction.LandChoiceSubmitted(listOf("land-2"))).effect)
    }

    @Test
    fun `a fresh question clears the retained clarification wording`() {
        val typedAgain = clarified()
            .reduce(ChatHomeAction.QuestionChanged("¿Y en el otro?"))
            .state
        val resubmitted = typedAgain.reduce(ChatHomeAction.AskClicked).state

        assertNull(resubmitted.clarificationQuestion)
        assertNull(resubmitted.lastResponseStatus)
        assertTrue(resubmitted.landIdsToChoose.isEmpty())
    }

    @Test
    fun `a selected effect keeps only the chosen stored lands in repository order`() {
        val lands = listOf(
            land("land-1", name = "Los Olivos", water = LocalWaterRegime.IRRIGATED),
            land("land-2", name = "La Loma", water = LocalWaterRegime.DRYLAND),
            land("land-3", name = "El Cerro", water = LocalWaterRegime.IRRIGATED),
        )

        val request = ChatEffect.SubmitSelected("¿Puedo regar hoy?", listOf("land-3", "land-1")).request(lands)

        assertEquals("¿Puedo regar hoy?", request.question)
        assertEquals(LandContextMode.selected, request.land_context.mode)
        // Repository order, not selection order; the un-chosen land is never sent.
        assertEquals(listOf("land-1", "land-3"), request.land_context.lands.map { it.id })
        // Only the needed attribute is carried; no name, municipality, or production method appears.
        request.land_context.lands.forEach { chosen ->
            assertNotNull(chosen.water_regime)
            assertNull(chosen.municipality)
            assertNull(chosen.production_method)
        }
    }

    @Test
    fun `a selected effect ignores an id that is not stored locally`() {
        val request = ChatEffect.SubmitSelected("¿Puedo regar hoy?", listOf("land-1", "ghost"))
            .request(listOf(land("land-1")))

        assertEquals(listOf("land-1"), request.land_context.lands.map { it.id })
        assertEquals(LandContextMode.selected, request.land_context.mode)
    }

    @Test
    fun `a selected effect with no stored chosen land degrades to the accepted general request`() {
        val request = ChatEffect.SubmitSelected("¿Puedo regar hoy?", listOf("ghost"))
            .request(listOf(land("land-1")))

        assertEquals(LandContextMode.general, request.land_context.mode)
        assertTrue(request.land_context.lands.isEmpty())
    }
}
