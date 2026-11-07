package com.jamarglex.manijero

import com.jamarglex.manijero.chat.AnswerRating
import com.jamarglex.manijero.chat.AnswerService
import com.jamarglex.manijero.chat.AnswerServiceErrorException
import com.jamarglex.manijero.chat.AnswerServiceUnavailableException
import com.jamarglex.manijero.chat.AnswerSource
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskRequest
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.chat.UnavailableAnswerService
import com.jamarglex.manijero.chat.WaterRegime
import com.jamarglex.manijero.chat.generalAskRequest
import com.jamarglex.manijero.inspector.AnswerInspection
import com.jamarglex.manijero.inspector.InspectionOutcome
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.lands.ProductionMethod as LocalProductionMethod
import com.jamarglex.manijero.lands.WaterRegime as LocalWaterRegime
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** The pinned code-owned `no_evidence` abstention message, taken verbatim from the accepted contract. */
private const val PINNED_NO_EVIDENCE =
    "No he encontrado esta información en los documentos oficiales que tengo. " +
        "Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."

@OptIn(ExperimentalCoroutinesApi::class)
class ChatConversationTest {
    private val originalQuestion = "  ¿Puedo regar hoy?  "

    private fun response(
        answer: String = "Una respuesta.",
        sources: List<AnswerSource> = emptyList(),
        landScope: LandContextMode = LandContextMode.general,
    ) = AskResponse(
        status = AnswerStatus.answered,
        answer = answer,
        sources = sources,
        land_scope = landScope,
        land_ids_to_choose = emptyList(),
    )

    private fun abstainedResponse(answer: String = PINNED_NO_EVIDENCE) = AskResponse(
        status = AnswerStatus.abstained,
        answer = answer,
        sources = emptyList(),
        land_scope = LandContextMode.general,
        land_ids_to_choose = emptyList(),
    )

    private class GatedAnswerService : AnswerService {
        val requests = mutableListOf<AskRequest>()
        private val gate = CompletableDeferred<AskResponse>()

        override suspend fun ask(request: AskRequest): AskResponse {
            requests += request
            return gate.await()
        }

        fun complete(response: AskResponse) {
            gate.complete(response)
        }
    }

    /** Fails with [failures] in order, then answers; records every request it received. */
    private class ScriptedAnswerService(
        private val failures: List<Throwable>,
        private val answer: AskResponse,
    ) : AnswerService {
        val requests = mutableListOf<AskRequest>()

        override suspend fun ask(request: AskRequest): AskResponse {
            requests += request
            val attempt = requests.lastIndex
            if (attempt < failures.size) throw failures[attempt]
            return answer
        }
    }

    private fun land(
        id: String,
        name: String = "Terreno",
        municipality: String? = null,
        waterRegime: LocalWaterRegime = LocalWaterRegime.UNKNOWN,
        productionMethod: LocalProductionMethod = LocalProductionMethod.UNKNOWN,
    ) = Land(
        id = id,
        name = name,
        zone = "El Llano",
        municipality = municipality,
        waterRegime = waterRegime,
        productionMethod = productionMethod,
        areaHectares = null,
        notes = null,
        createdAtEpochMillis = 1L,
        updatedAtEpochMillis = 1L,
    )

    @Test
    fun `repeated clicks produce one request and one reply`() = runTest {
        val service = GatedAnswerService()
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        runCurrent()
        conversation.onAction(ChatHomeAction.AskClicked)
        runCurrent()

        assertEquals(1, service.requests.size)
        assertEquals(originalQuestion, service.requests.single().question)
        assertEquals(SubmissionPhase.SUBMITTING, conversation.state.phase)

        service.complete(response("Respuesta única."))
        advanceUntilIdle()

        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.ASSISTANT })
        assertEquals("Respuesta única.", conversation.state.messages.last().text)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `each answered and abstained entry keeps its own inspection and a plain one has none`() = runTest {
        fun inspection(total: Long) = AnswerInspection(
            schema = "answer-inspection-v1",
            outcome = InspectionOutcome(cited_passage_ids = emptyList()),
            total_ms = total,
        )
        val responses = listOf(
            response("Primera.").copy(inspection = inspection(1)),
            abstainedResponse().copy(inspection = inspection(2)),
            response("Tercera."),
        )
        val service = object : AnswerService {
            var next = 0
            override suspend fun ask(request: AskRequest): AskResponse = responses[next++]
        }
        val conversation = ChatConversation(service, this)

        repeat(3) { index ->
            conversation.onAction(ChatHomeAction.QuestionChanged("Pregunta $index"))
            conversation.onAction(ChatHomeAction.AskClicked)
            advanceUntilIdle()
        }

        val assistant = conversation.state.messages.filter { it.speaker == Speaker.ASSISTANT }
        assertEquals(listOf(1L, 2L, null), assistant.map { it.inspection?.total_ms })
    }

    @Test
    fun `an answered response keeps its decoded sources on the assistant entry`() = runTest {
        val sources = listOf(
            AnswerSource(
                title = "Solicitud única de la PAC",
                issuing_body = "Ministerio de Agricultura, Pesca y Alimentación",
                url = "https://www.mapa.gob.es/",
                location = "Información de la solicitud única",
                published_or_updated_on = "2026-01-15",
                verified_on = "2026-10-01",
                excerpt = "La solicitud única es el procedimiento anual.",
            ),
        )
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse =
                response(answer = "La solicitud única es anual. [1]", sources = sources)
        }
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.USER })
        val assistant = conversation.state.messages.single { it.speaker == Speaker.ASSISTANT }
        assertEquals(sources, assistant.sources)
        assertEquals(AnswerStatus.answered, assistant.answerStatus)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `an answered response with a non-general scope carries it on the assistant entry`() = runTest {
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse =
                response(answer = "Para el terreno elegido.", landScope = LandContextMode.selected)
        }
        val conversation = ChatConversation(service, this, landsProvider = { emptyList() })

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.USER })
        val assistant = conversation.state.messages.single { it.speaker == Speaker.ASSISTANT }
        assertEquals(LandContextMode.selected, assistant.landScope)
        assertEquals(AnswerStatus.answered, assistant.answerStatus)
        assertEquals("Para el terreno elegido.", assistant.text)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `an abstained response arrives once with its state and is never a failure`() = runTest {
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse = abstainedResponse()
        }
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.USER })
        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.ASSISTANT })
        val assistant = conversation.state.messages.single { it.speaker == Speaker.ASSISTANT }
        assertEquals(AnswerStatus.abstained, assistant.answerStatus)
        assertEquals(PINNED_NO_EVIDENCE, assistant.text)
        assertNull(conversation.state.failure)
        assertNull(conversation.state.failedQuestion)
        assertEquals(AnswerStatus.abstained, conversation.state.lastResponseStatus)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `a transport failure releases the composer without inventing a reply`() = runTest {
        val failingService = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse =
                error("no answer endpoint is configured")
        }
        val conversation = ChatConversation(failingService, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
        assertEquals(originalQuestion, conversation.state.question)
        assertEquals(1, conversation.state.messages.size)
        assertNull(conversation.state.lastResponseStatus)
        assertEquals(RequestFailure.SERVICE_ERROR, conversation.state.failure)
        assertEquals(originalQuestion, conversation.state.failedQuestion)
    }

    @Test
    fun `the default wiring fails instead of fabricating an answer`() = runTest {
        val conversation = ChatConversation(UnavailableAnswerService, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(1, conversation.state.messages.size)
        assertEquals(originalQuestion, conversation.state.question)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
        assertEquals(RequestFailure.SERVICE_ERROR, conversation.state.failure)
    }

    @Test
    fun `an unreachable service is reported as could not reach`() = runTest {
        val service = ScriptedAnswerService(
            failures = listOf(AnswerServiceUnavailableException()),
            answer = response(),
        )
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(RequestFailure.COULD_NOT_REACH_SERVICE, conversation.state.failure)
        assertEquals(originalQuestion, conversation.state.failedQuestion)
        assertEquals(originalQuestion, conversation.state.question)
        assertEquals(1, conversation.state.messages.size)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `a service error is reported as a service error`() = runTest {
        val service = ScriptedAnswerService(
            failures = listOf(AnswerServiceErrorException()),
            answer = response(),
        )
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(RequestFailure.SERVICE_ERROR, conversation.state.failure)
        assertEquals(originalQuestion, conversation.state.failedQuestion)
        assertEquals(1, conversation.state.messages.size)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `retry resends the exact wording and adds one user message and one answer`() = runTest {
        val gate = CompletableDeferred<AskResponse>()
        val requests = mutableListOf<AskRequest>()
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse {
                requests += request
                if (requests.size == 1) throw AnswerServiceUnavailableException()
                return gate.await()
            }
        }
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        assertEquals(1, requests.size)
        assertEquals(RequestFailure.COULD_NOT_REACH_SERVICE, conversation.state.failure)

        conversation.onAction(ChatHomeAction.RetryClicked)
        runCurrent()

        assertEquals(SubmissionPhase.SUBMITTING, conversation.state.phase)
        assertNull(conversation.state.failure)

        // While the retry is in flight the action is not actionable: no third request.
        val attemptsAfterRetry = requests.size
        conversation.onAction(ChatHomeAction.RetryClicked)
        runCurrent()
        assertEquals(attemptsAfterRetry, requests.size)
        assertEquals(SubmissionPhase.SUBMITTING, conversation.state.phase)

        gate.complete(response("Respuesta única."))
        advanceUntilIdle()

        assertEquals(2, requests.size)
        assertEquals(originalQuestion, requests.last().question)
        assertEquals(2, conversation.state.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), conversation.state.messages[0])
        assertEquals(ChatMessage(Speaker.ASSISTANT, "Respuesta única."), conversation.state.messages[1])
        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.USER })
        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.ASSISTANT })
        assertNull(conversation.state.failure)
        assertNull(conversation.state.failedQuestion)
        assertEquals("", conversation.state.question)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `a retry that fails again keeps one user message and stays retryable`() = runTest {
        val service = ScriptedAnswerService(
            failures = listOf(
                AnswerServiceErrorException(),
                AnswerServiceUnavailableException(),
            ),
            answer = response("Respuesta única."),
        )
        val conversation = ChatConversation(service, this)

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()
        conversation.onAction(ChatHomeAction.RetryClicked)
        advanceUntilIdle()

        assertEquals(2, service.requests.size)
        assertTrue(service.requests.all { it.question == originalQuestion })
        assertEquals(1, conversation.state.messages.size)
        assertEquals(ChatMessage(Speaker.USER, originalQuestion), conversation.state.messages.single())
        assertEquals(RequestFailure.COULD_NOT_REACH_SERVICE, conversation.state.failure)
        assertEquals(originalQuestion, conversation.state.failedQuestion)
        assertEquals(originalQuestion, conversation.state.question)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)

        val thirdAttempt = conversation.state.reduce(ChatHomeAction.RetryClicked)
        assertEquals(SubmissionPhase.SUBMITTING, thirdAttempt.state.phase)
        assertEquals(originalQuestion, (thirdAttempt.effect as ChatEffect.Submit).question)
    }

    @Test
    fun `with no stored land the request stays the accepted general payload`() = runTest {
        val service = GatedAnswerService()
        val conversation = ChatConversation(service, this, landsProvider = { emptyList() })

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        runCurrent()

        val request = service.requests.single()
        assertEquals(generalAskRequest(originalQuestion), request)
        assertEquals(LandContextMode.general, request.land_context.mode)
        assertTrue(request.land_context.lands.isEmpty())

        service.complete(response("Respuesta única."))
        advanceUntilIdle()
        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.ASSISTANT })
    }

    @Test
    fun `a land-relevant submit carries every land and the attribute the question needs`() = runTest {
        val service = GatedAnswerService()
        val lands = listOf(
            land(
                id = "land-1",
                name = "Los Olivos",
                municipality = "Martos",
                waterRegime = LocalWaterRegime.IRRIGATED,
                productionMethod = LocalProductionMethod.ORGANIC,
            ),
            land(id = "land-2", name = "La Loma"),
        )
        val conversation = ChatConversation(service, this, landsProvider = { lands })

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        runCurrent()

        val request = service.requests.single()
        assertEquals(originalQuestion, request.question)
        assertEquals(LandContextMode.all_active, request.land_context.mode)
        assertEquals(listOf("land-1", "land-2"), request.land_context.lands.map { it.id })
        assertEquals(WaterRegime.irrigated, request.land_context.lands[0].water_regime)
        assertEquals(WaterRegime.unknown, request.land_context.lands[1].water_regime)
        assertNull(request.land_context.lands[0].municipality)
        assertNull(request.land_context.lands[0].production_method)

        service.complete(response("Respuesta única."))
        advanceUntilIdle()
        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.ASSISTANT })
    }

    @Test
    fun `a retry re-reads the lands stored at that moment`() = runTest {
        var current = listOf(land("land-1", name = "Los Olivos"))
        val service = ScriptedAnswerService(
            failures = listOf(AnswerServiceUnavailableException()),
            answer = response("Respuesta única."),
        )
        val conversation = ChatConversation(service, this, landsProvider = { current })

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()
        assertEquals(listOf("land-1"), service.requests.single().land_context.lands.map { it.id })

        // A land added after the chat screen opened is included by the retry, wording unchanged.
        current = current + land("land-2", name = "La Loma")
        conversation.onAction(ChatHomeAction.RetryClicked)
        advanceUntilIdle()

        assertEquals(2, service.requests.size)
        val retry = service.requests.last()
        assertEquals(originalQuestion, retry.question)
        assertEquals(listOf("land-1", "land-2"), retry.land_context.lands.map { it.id })
        assertNull(conversation.state.failure)
    }

    @Test
    fun `a failing land read still submits the accepted general request`() = runTest {
        val service = GatedAnswerService()
        val conversation = ChatConversation(
            service,
            this,
            landsProvider = { error("land store unavailable") },
        )

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        runCurrent()

        val request = service.requests.single()
        assertEquals(originalQuestion, request.question)
        assertEquals(LandContextMode.general, request.land_context.mode)
        assertTrue(request.land_context.lands.isEmpty())

        service.complete(response("Respuesta única."))
        advanceUntilIdle()

        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.ASSISTANT })
        assertNull(conversation.state.failure)
    }

    @Test
    fun `a clarification resubmits the exact wording as a selected request with only the chosen land`() = runTest {
        val lands = listOf(
            land(id = "land-1", name = "Los Olivos", waterRegime = LocalWaterRegime.IRRIGATED),
            land(id = "land-2", name = "La Loma", waterRegime = LocalWaterRegime.DRYLAND),
        )
        val requests = mutableListOf<AskRequest>()
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse {
                requests += request
                return if (requests.size == 1) {
                    AskResponse(
                        status = AnswerStatus.needs_land_clarification,
                        answer = "",
                        sources = emptyList(),
                        land_scope = LandContextMode.selected,
                        land_ids_to_choose = listOf("land-1", "land-2"),
                    )
                } else {
                    response("Respuesta para el terreno elegido.")
                }
            }
        }
        val conversation = ChatConversation(service, this, landsProvider = { lands })

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        // The first request carries every land and asks the service to choose; no answer is invented.
        assertEquals(1, requests.size)
        assertEquals(LandContextMode.all_active, requests.single().land_context.mode)
        assertTrue(conversation.state.awaitingLandClarification)
        assertEquals(listOf("land-1", "land-2"), conversation.state.landIdsToChoose)
        assertEquals(originalQuestion, conversation.state.clarificationQuestion)
        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.USER })
        assertEquals(0, conversation.state.messages.count { it.speaker == Speaker.ASSISTANT })

        conversation.onAction(ChatHomeAction.LandChoiceSubmitted(listOf("land-1")))
        advanceUntilIdle()

        assertEquals(2, requests.size)
        val selected = requests.last()
        assertEquals(originalQuestion, selected.question)
        assertEquals(LandContextMode.selected, selected.land_context.mode)
        assertEquals(listOf("land-1"), selected.land_context.lands.map { it.id })
        assertEquals(WaterRegime.irrigated, selected.land_context.lands.single().water_regime)
        assertNull(selected.land_context.lands.single().production_method)
        // No second user message: the transcript keeps exactly the original entry plus one answer.
        assertEquals(1, conversation.state.messages.count { it.speaker == Speaker.USER })
        assertEquals("Respuesta para el terreno elegido.", conversation.state.messages.last().text)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
    }

    @Test
    fun `a land choice for a land removed meanwhile degrades to the accepted general request`() = runTest {
        var current = listOf(land("land-1", name = "Los Olivos"), land("land-2", name = "La Loma"))
        val requests = mutableListOf<AskRequest>()
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse {
                requests += request
                return if (requests.size == 1) {
                    AskResponse(
                        status = AnswerStatus.needs_land_clarification,
                        answer = "",
                        sources = emptyList(),
                        land_scope = LandContextMode.selected,
                        land_ids_to_choose = listOf("land-1", "land-2"),
                    )
                } else {
                    response("Respuesta única.")
                }
            }
        }
        val conversation = ChatConversation(service, this, landsProvider = { current })

        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()

        // The chosen land is removed before the person confirms: the wording is resent as general.
        current = listOf(land("land-1", name = "Los Olivos"))
        conversation.onAction(ChatHomeAction.LandChoiceSubmitted(listOf("land-2")))
        advanceUntilIdle()

        assertEquals(2, requests.size)
        val resubmitted = requests.last()
        assertEquals(originalQuestion, resubmitted.question)
        assertEquals(LandContextMode.general, resubmitted.land_context.mode)
        assertTrue(resubmitted.land_context.lands.isEmpty())
    }

    // One-tap answer feedback: exactly one rating per tap, and the conversation's question, composer,
    // failure and clarification stay untouched.

    private fun TestScope.answerOne(conversation: ChatConversation) {
        conversation.onAction(ChatHomeAction.QuestionChanged(originalQuestion))
        conversation.onAction(ChatHomeAction.AskClicked)
        advanceUntilIdle()
    }

    @Test
    fun `a rating is sent once and locks only that answer`() = runTest {
        val ratings = mutableListOf<AnswerRating>()
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse = response("Una respuesta.")
            override suspend fun sendFeedback(rating: AnswerRating) {
                ratings += rating
            }
        }
        val conversation = ChatConversation(service, this)
        answerOne(conversation)

        conversation.onAction(ChatHomeAction.FeedbackClicked(messageIndex = 1, rating = AnswerRating.USEFUL))
        advanceUntilIdle()

        assertEquals(listOf(AnswerRating.USEFUL), ratings)
        assertEquals(AnswerFeedback.Sent(AnswerRating.USEFUL), conversation.state.messages[1].feedback)
        assertEquals(2, conversation.state.messages.size)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)
        assertNull(conversation.state.failure)

        // The locked answer never sends a second rating, whichever control is tapped.
        conversation.onAction(
            ChatHomeAction.FeedbackClicked(messageIndex = 1, rating = AnswerRating.NOT_USEFUL),
        )
        advanceUntilIdle()

        assertEquals(listOf(AnswerRating.USEFUL), ratings)
        assertEquals(AnswerFeedback.Sent(AnswerRating.USEFUL), conversation.state.messages[1].feedback)
    }

    @Test
    fun `a failed rating keeps the answer rateable and adds no transcript or failure`() = runTest {
        var fail = true
        val ratings = mutableListOf<AnswerRating>()
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse = response("Una respuesta.")
            override suspend fun sendFeedback(rating: AnswerRating) {
                ratings += rating
                if (fail) error("the rating was not accepted")
            }
        }
        val conversation = ChatConversation(service, this)
        answerOne(conversation)
        val before = conversation.state

        conversation.onAction(ChatHomeAction.FeedbackClicked(messageIndex = 1, rating = AnswerRating.USEFUL))
        advanceUntilIdle()

        assertEquals(AnswerFeedback.Failed(AnswerRating.USEFUL), conversation.state.messages[1].feedback)
        assertEquals(before.messages, conversation.state.messages.map { it.copy(feedback = AnswerFeedback.None) })
        assertNull(conversation.state.failure)
        assertNull(conversation.state.failedQuestion)
        assertEquals(SubmissionPhase.IDLE, conversation.state.phase)

        // An honest retry sends exactly one new rating for the same answer.
        fail = false
        conversation.onAction(
            ChatHomeAction.FeedbackClicked(messageIndex = 1, rating = AnswerRating.NOT_USEFUL),
        )
        advanceUntilIdle()

        assertEquals(listOf(AnswerRating.USEFUL, AnswerRating.NOT_USEFUL), ratings)
        assertEquals(AnswerFeedback.Sent(AnswerRating.NOT_USEFUL), conversation.state.messages[1].feedback)
    }

    @Test
    fun `a service without feedback reports the honest failure`() = runTest {
        val service = object : AnswerService {
            override suspend fun ask(request: AskRequest): AskResponse = response("Una respuesta.")
        }
        val conversation = ChatConversation(service, this)
        answerOne(conversation)

        conversation.onAction(ChatHomeAction.FeedbackClicked(messageIndex = 1, rating = AnswerRating.USEFUL))
        advanceUntilIdle()

        assertEquals(AnswerFeedback.Failed(AnswerRating.USEFUL), conversation.state.messages[1].feedback)
        assertEquals(2, conversation.state.messages.size)
    }
}
