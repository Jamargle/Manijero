package com.jamarglex.manijero.smoke

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import com.jamarglex.manijero.chat.KtorAnswerService
import com.jamarglex.manijero.chat.answerHttpClient
import com.jamarglex.manijero.connection.ActiveServiceAddress
import com.jamarglex.manijero.connection.ConnectionTools
import com.jamarglex.manijero.connection.KtorServiceStatusChecker
import com.jamarglex.manijero.connection.LOCAL_SMOKE_QUESTION
import com.jamarglex.manijero.connection.ReadOnlyServiceAddressStore
import com.jamarglex.manijero.connection.ServiceAddressSource
import com.jamarglex.manijero.connection.ServiceAddressStore
import com.jamarglex.manijero.connection.SmokeOutcome
import com.jamarglex.manijero.connection.SmokeReport
import com.jamarglex.manijero.connection.smokeResultLine
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
import kotlinx.coroutines.runBlocking
import kotlinx.io.IOException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * The Desktop smoke driver against a Ktor `MockEngine` serving the committed contract examples. No
 * real network, service, or window is used: the shared `App` renders offscreen. Each case checks the
 * outcome the driver reports, the requests it sent, and that the saved address is never written.
 */
@OptIn(ExperimentalTestApi::class)
class DesktopSmokeDriverTest {
    private val examples = contractExamplesDirectory()
    private val answered = File(examples, "response-answered.json").readText()
    private val abstained = File(examples, "response-abstained.json").readText()
    private val clarification = File(examples, "response-needs-land-clarification.json").readText()
    private val answeredWithoutSources = JsonObject(
        Json.parseToJsonElement(answered).jsonObject + ("sources" to JsonArray(emptyList())),
    ).toString()

    @Test
    fun anAnswerWithSourcesPassesAndSendsOneGeneralQuestion() {
        val run = smoke(ask = { json(answered) })

        assertEquals(SmokeOutcome.Answered, run.report.outcome)
        assertTrue(run.report.sources >= 1)
        assertEquals(listOf("/health", "/ready", "/ask"), run.paths)
        val body = Json.parseToJsonElement(run.askBodies.single()).jsonObject
        assertEquals(setOf("question", "land_context"), body.keys, "no retention key")
        assertEquals(LOCAL_SMOKE_QUESTION, body.getValue("question").jsonPrimitive.content)
        assertEquals(Json.parseToJsonElement("""{"mode":"general","lands":[]}"""), body.getValue("land_context"))
        assertFalse(LOCAL_SMOKE_QUESTION in smokeResultLine(run.report))
        assertEquals(0, run.store.writes)
    }

    @Test
    fun anAbstentionPasses() {
        val run = smoke(ask = { json(abstained) })

        assertEquals(SmokeOutcome.Abstained, run.report.outcome)
        assertEquals(0, run.report.sources)
    }

    @Test
    fun anAnswerWithoutASourceCardFails() {
        assertEquals(SmokeOutcome.AnsweredWithoutSources, smoke(ask = { json(answeredWithoutSources) }).report.outcome)
    }

    @Test
    fun aLandClarificationFails() {
        assertEquals(SmokeOutcome.LandClarification, smoke(ask = { json(clarification) }).report.outcome)
    }

    @Test
    fun aServiceThatIsNotReadyIsReportedWithoutAsking() {
        val run = smoke(ready = { json("""{"status":"unavailable"}""", HttpStatusCode.ServiceUnavailable) }, ask = { json(answered) })

        assertEquals(SmokeOutcome.NotReady, run.report.outcome)
        assertEquals(listOf("/health", "/ready"), run.paths)
    }

    @Test
    fun oneRetryAfterAnUnreachableFailureCanStillPass() {
        var asks = 0
        val run = smoke(ask = { if (asks++ == 0) throw IOException("first question timed out") else json(answered) })

        assertEquals(SmokeOutcome.Answered, run.report.outcome)
        assertEquals(listOf("/health", "/ready", "/ask", "/ask"), run.paths)
    }

    @Test
    fun aSecondUnreachableFailureIsNotRetriedAgain() {
        val run = smoke(ask = { throw IOException("still loading") })

        assertEquals(SmokeOutcome.Unreachable, run.report.outcome)
        assertEquals(listOf("/health", "/ready", "/ask", "/ask"), run.paths)
    }

    @Test
    fun aServiceErrorFailsWithoutARetry() {
        val run = smoke(ask = { json("""{"detail":"boom"}""", HttpStatusCode.InternalServerError) })

        assertEquals(SmokeOutcome.ServiceError, run.report.outcome)
        assertEquals(listOf("/health", "/ready", "/ask"), run.paths)
    }

    @Test
    fun noReplyWithinTheBoundIsNoAnswer() {
        val never = CompletableDeferred<Unit>()
        val run = smoke(replyTimeoutMillis = 1_500, ask = { never.await(); json(answered) })

        assertEquals(SmokeOutcome.NoAnswer, run.report.outcome)
    }

    @Test
    fun aSavedAddressThatIsNotTheServiceAddressSendsNothing() {
        val run = smoke(stored = "http://192.168.1.20:8000", ask = { json(answered) })

        assertEquals(
            SmokeReport(SmokeOutcome.OtherAddress, 0, ServiceAddressSource.Saved, "http://192.168.1.20:8000"),
            run.report,
        )
        assertEquals(emptyList(), run.paths)
        assertEquals(0, run.store.writes)
    }

    @Test
    fun theSavedAddressIsUsedWhenItIsTheServiceAddress() {
        val run = smoke(stored = "$DEFAULT/", ask = { json(abstained) })

        assertEquals(SmokeOutcome.Abstained, run.report.outcome)
        assertEquals(ServiceAddressSource.Saved, run.report.source)
        assertEquals(0, run.store.writes)
    }

    // --- Harness -------------------------------------------------------------------------------

    private class RecordingStore(private val stored: String?) : ServiceAddressStore {
        var writes = 0
        override fun load(): String? = stored
        override fun save(address: String) { writes++ }
        override fun clear() { writes++ }
    }

    private class Run(val report: SmokeReport, val paths: List<String>, val askBodies: List<String>, val store: RecordingStore)

    private fun smoke(
        stored: String? = null,
        replyTimeoutMillis: Long = 20_000,
        ready: suspend MockRequestHandleScope.() -> HttpResponseData = { json("""{"status":"ready"}""") },
        ask: suspend MockRequestHandleScope.() -> HttpResponseData,
    ): Run {
        val paths = mutableListOf<String>()
        val askBodies = mutableListOf<String>()
        val engine = MockEngine { request: HttpRequestData ->
            synchronized(paths) { paths += request.url.encodedPath }
            assertEquals("127.0.0.1", request.url.host)
            when (request.url.encodedPath) {
                "/health" -> json("""{"status":"ok","service":"manijero-backend"}""")
                "/ready" -> ready()
                "/ask" -> {
                    assertEquals(HttpMethod.Post, request.method)
                    synchronized(askBodies) { askBodies += request.body.asText() }
                    ask()
                }
                else -> json("{}", HttpStatusCode.NotFound)
            }
        }
        val client = answerHttpClient(engine)
        val store = RecordingStore(stored)
        val address = ActiveServiceAddress(DEFAULT, ReadOnlyServiceAddressStore(store))
        val tools = ConnectionTools(address, KtorServiceStatusChecker(client))
        val script = SmokeUiScript(tools, KtorAnswerService(client, address::current), DEFAULT, replyTimeoutMillis)
        try {
            val report = runBlocking { script.preflight() } ?: run {
                lateinit var asked: SmokeReport
                runDesktopComposeUiTest(width = 900, height = 1600) { asked = script.ask(this) }
                asked
            }
            return Run(report, synchronized(paths) { paths.toList() }, synchronized(askBodies) { askBodies.toList() }, store)
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
        const val DEFAULT = "http://127.0.0.1:8000"
    }
}
