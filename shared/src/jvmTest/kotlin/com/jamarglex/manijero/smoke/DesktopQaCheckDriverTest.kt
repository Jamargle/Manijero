package com.jamarglex.manijero.smoke

import com.jamarglex.manijero.chat.PilotToken
import com.jamarglex.manijero.chat.answerHttpClient
import com.jamarglex.manijero.connection.LOCAL_SMOKE_QUESTION
import com.jamarglex.manijero.connection.ServiceAddressStore
import com.jamarglex.manijero.platform.DesktopEnvironment
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.MockRequestHandleScope
import io.ktor.client.engine.mock.respond
import io.ktor.client.request.HttpRequestData
import io.ktor.client.request.HttpResponseData
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpMethod
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.OutgoingContent
import io.ktor.http.content.TextContent
import io.ktor.http.headersOf
import kotlinx.coroutines.CompletableDeferred
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * The QA Desktop check driver against a Ktor `MockEngine` over an https base URL with a fake access
 * key. No real network, QA service, or window is used; the shared `App` renders offscreen. Each case
 * checks the one result line, the requests sent, the bearer header, and that the saved address is
 * never written.
 */
class DesktopQaCheckDriverTest {
    private val examples = contractExamplesDirectory()
    private val answered = File(examples, "response-answered.json").readText()
    private val abstained = File(examples, "response-abstained.json").readText()
    private val clarification = File(examples, "response-needs-land-clarification.json").readText()
    private val answeredWithoutSources = JsonObject(
        Json.parseToJsonElement(answered).jsonObject + ("sources" to JsonArray(emptyList())),
    ).toString()

    @Test
    fun anAnswerWithSourcesAndAcceptedFeedbackPasses() {
        val run = check(ask = { json(answered) })

        assertTrue(run.line.matches(Regex("""MANIJERO_QA_CHECK_RESULT outcome=answered sources=[1-9][0-9]* feedback=sent address=default url=$QA""")), run.line)
        assertEquals(listOf("/health", "/ready", "/ask", "/feedback"), run.paths)
        assertEquals("""{"rating":"useful"}""", run.feedbackBodies.single().replace(" ", ""))
        assertEquals(setOf("Bearer $FAKE_TOKEN"), run.bearers.toSet(), "ask and feedback carry the bearer over https")
        assertEquals(2, run.bearers.size)
        assertEquals(0, run.store.writes)
        assertFalse(FAKE_TOKEN in run.line || LOCAL_SMOKE_QUESTION in run.line)
    }

    @Test
    fun theQuestionIsTheFixedGeneralOneWithNoLands() {
        val run = check(ask = { json(answered) })

        val body = Json.parseToJsonElement(run.askBodies.single()).jsonObject
        assertEquals(setOf("question", "land_context"), body.keys, "no retention key")
        assertEquals(Json.parseToJsonElement("""{"mode":"general","lands":[]}"""), body.getValue("land_context"))
        assertTrue(LOCAL_SMOKE_QUESTION in run.askBodies.single())
    }

    @Test
    fun aFailedFeedbackIsReportedAfterOneAttempt() {
        val run = check(ask = { json(answered) }, feedback = { json("{}", HttpStatusCode.InternalServerError) })

        assertTrue(" feedback=failed " in run.line && " outcome=answered " in run.line, run.line)
        assertEquals(1, run.feedbackBodies.size, "exactly one rating is sent")
    }

    @Test
    fun aFeedbackAddressNotFoundMeansQaHasNoFeedbackYet() {
        val run = check(ask = { json(answered) }, feedback = { json("{}", HttpStatusCode.NotFound) })

        assertTrue(" outcome=answered " in run.line && " feedback=not_on_qa " in run.line, run.line)
        assertEquals(1, run.feedbackBodies.size, "exactly one rating is sent")
    }

    @Test
    fun anAbstentionFailsTheAnswerButStillRates() {
        val run = check(ask = { json(abstained) })

        assertTrue(" outcome=abstained sources=0 feedback=sent " in run.line, run.line)
        assertEquals(1, run.feedbackBodies.size)
    }

    @Test
    fun anAnswerWithoutSourceCardsIsReportedAndRated() {
        val run = check(ask = { json(answeredWithoutSources) })

        assertTrue(" outcome=answered_without_sources sources=0 feedback=sent " in run.line, run.line)
    }

    @Test
    fun aLandClarificationSendsNoRating() {
        val run = check(ask = { json(clarification) })

        assertTrue(" outcome=land_clarification " in run.line && " feedback=not_tried " in run.line, run.line)
        assertEquals(emptyList(), run.feedbackBodies)
    }

    @Test
    fun aServiceErrorSendsNoRating() {
        val run = check(ask = { json("""{"detail":"boom"}""", HttpStatusCode.InternalServerError) })

        assertTrue(" outcome=service_error " in run.line && " feedback=not_tried " in run.line, run.line)
        assertEquals(listOf("/health", "/ready", "/ask"), run.paths)
    }

    @Test
    fun aFeedbackThatNeverAnswersIsNoReply() {
        val never = CompletableDeferred<Unit>()
        val run = check(
            feedbackTimeoutMillis = 1_500,
            ask = { json(answered) },
            feedback = { never.await(); json("{}") },
        )

        assertTrue(" outcome=answered " in run.line && " feedback=no_reply " in run.line, run.line)
    }

    @Test
    fun aSavedAddressThatIsNotTheQaAddressSendsNothing() {
        val run = check(stored = "https://other.example.org", ask = { json(answered) })

        assertEquals(
            "MANIJERO_QA_CHECK_RESULT outcome=other_address sources=0 feedback=not_tried address=saved url=https://other.example.org",
            run.line,
        )
        assertEquals(emptyList(), run.paths)
        assertEquals(0, run.store.writes)
    }

    @Test
    fun aBuildThatIsNotQaIsNotRun() {
        val run = check(environment = DesktopEnvironment.Local, ask = { json(answered) })

        assertEquals(
            "MANIJERO_QA_CHECK_RESULT outcome=not_qa_build sources=0 feedback=not_tried address=default url=invalid",
            run.line,
        )
        assertEquals(emptyList(), run.paths)
    }

    @Test
    fun aBuildWithoutAnAccessKeyIsNotRun() {
        val run = check(token = null, ask = { json(answered) })

        assertEquals(
            "MANIJERO_QA_CHECK_RESULT outcome=no_access_key sources=0 feedback=not_tried address=default url=invalid",
            run.line,
        )
        assertEquals(emptyList(), run.paths)
    }

    @Test
    fun theFakeTokenShapeIsAValidAccessKey() {
        assertNotNull(PilotToken.fromBuildSetting(FAKE_TOKEN))
    }

    // --- Harness -------------------------------------------------------------------------------

    private class RecordingStore(private val stored: String?) : ServiceAddressStore {
        var writes = 0
        override fun load(): String? = stored
        override fun save(address: String) { writes++ }
        override fun clear() { writes++ }
    }

    private class Run(
        val line: String,
        val paths: List<String>,
        val askBodies: List<String>,
        val feedbackBodies: List<String>,
        val bearers: List<String>,
        val store: RecordingStore,
    )

    private fun check(
        environment: DesktopEnvironment = DesktopEnvironment.Qa(QA),
        token: PilotToken? = PilotToken.fromBuildSetting(FAKE_TOKEN),
        stored: String? = null,
        feedbackTimeoutMillis: Long = 20_000,
        ask: suspend MockRequestHandleScope.() -> HttpResponseData,
        feedback: suspend MockRequestHandleScope.() -> HttpResponseData = { respond("", HttpStatusCode.NoContent) },
    ): Run {
        val paths = mutableListOf<String>()
        val askBodies = mutableListOf<String>()
        val feedbackBodies = mutableListOf<String>()
        val bearers = mutableListOf<String>()
        val engine = MockEngine { request: HttpRequestData ->
            synchronized(paths) { paths += request.url.encodedPath }
            assertEquals("https", request.url.protocol.name)
            assertEquals("qa.example.org", request.url.host)
            request.headers[HttpHeaders.Authorization]?.let { synchronized(bearers) { bearers += it } }
            when (request.url.encodedPath) {
                "/health" -> json("""{"status":"ok","service":"manijero-backend"}""")
                "/ready" -> json("""{"status":"ready"}""")
                "/ask" -> {
                    assertEquals(HttpMethod.Post, request.method)
                    synchronized(askBodies) { askBodies += request.body.asText() }
                    ask()
                }
                "/feedback" -> {
                    assertEquals(HttpMethod.Post, request.method)
                    synchronized(feedbackBodies) { feedbackBodies += request.body.asText() }
                    feedback()
                }
                else -> json("{}", HttpStatusCode.NotFound)
            }
        }
        val client = answerHttpClient(engine)
        val store = RecordingStore(stored)
        try {
            val line = qaCheckLine(
                environment, token, client, store, QA,
                replyTimeoutMillis = 20_000, feedbackTimeoutMillis = feedbackTimeoutMillis,
            )
            return Run(
                line,
                synchronized(paths) { paths.toList() },
                synchronized(askBodies) { askBodies.toList() },
                synchronized(feedbackBodies) { feedbackBodies.toList() },
                synchronized(bearers) { bearers.toList() },
                store,
            )
        } finally {
            client.close()
        }
    }

    private fun MockRequestHandleScope.json(body: String, status: HttpStatusCode = HttpStatusCode.OK): HttpResponseData =
        respond(body, status, headersOf(HttpHeaders.ContentType, ContentType.Application.Json.toString()))

    private fun OutgoingContent.asText(): String = when (this) {
        is TextContent -> text
        is OutgoingContent.ByteArrayContent -> bytes().decodeToString()
        else -> error("Unsupported request body: $this")
    }

    private fun contractExamplesDirectory(): File {
        var directory: File? = File("").absoluteFile
        while (directory != null) {
            val candidate = File(directory, "contracts/examples")
            if (candidate.isDirectory) return candidate
            directory = directory.parentFile
        }
        error("Could not locate contracts/examples from ${File("").absolutePath}")
    }

    private companion object {
        const val QA = "https://qa.example.org"
        const val FAKE_TOKEN = "fake-qa-access-key-for-unit-tests-only-0123456789"
    }
}
