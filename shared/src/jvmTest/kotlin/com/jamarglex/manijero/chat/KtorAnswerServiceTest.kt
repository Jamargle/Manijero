package com.jamarglex.manijero.chat

import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.HttpTimeoutConfig
import io.ktor.client.plugins.plugin
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpMethod
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.OutgoingContent
import io.ktor.http.content.TextContent
import io.ktor.http.headersOf
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import kotlinx.io.IOException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Transport-level checks: the accepted contract example is the response body, the captured
 * outbound request must be exactly one general `POST /ask`, and every failure shape (stall, I/O
 * error, error status, undecodable body) must surface as a payload-free failure signal instead of
 * an answer.
 */
class KtorAnswerServiceTest {
    private val answeredFixture = File(contractExamplesDirectory(), "response-answered.json").readText()

    @Test
    fun `sends one general POST ask with the exact question and decodes the accepted fixture`() = runTest {
        val engine = MockEngine {
            respond(
                content = answeredFixture,
                status = HttpStatusCode.OK,
                headers = headersOf(HttpHeaders.ContentType, ContentType.Application.Json.toString()),
            )
        }
        val service = KtorAnswerService(
            client = answerHttpClient(engine),
            baseUrl = "https://api.example.invalid/",
        )

        val response = service.ask(generalAskRequest(question = "  ¿Puedo regar hoy?  "))

        val sent = engine.requestHistory.single()
        assertEquals(HttpMethod.Post, sent.method)
        assertEquals("/ask", sent.url.encodedPath)
        assertEquals("api.example.invalid", sent.url.host)
        assertEquals(ContentType.Application.Json, sent.body.contentType)

        val body = Json.parseToJsonElement(sent.body.asText()).jsonObject
        assertEquals(setOf("question", "land_context"), body.keys)
        assertEquals("  ¿Puedo regar hoy?  ", body.getValue("question").jsonPrimitive.content)
        assertEquals(
            Json.parseToJsonElement("""{"mode":"general","lands":[]}"""),
            body.getValue("land_context"),
        )

        assertEquals(AnswerStatus.answered, response.status)
        assertEquals(
            Json.parseToJsonElement(answeredFixture),
            Json.parseToJsonElement(answerJson.encodeToString(AskResponse.serializer(), response)),
        )
        assertEquals("general", response.land_scope.name)
        assertTrue(response.sources.isNotEmpty())
        assertTrue(response.land_ids_to_choose.isEmpty())
    }

    @Test
    fun `a request body omits unknown optional land attributes instead of sending nulls`() {
        val encoded = answerJson.encodeToString(
            AskRequest.serializer(),
            generalAskRequest("¿Puedo regar hoy?"),
        )

        assertEquals("""{"question":"¿Puedo regar hoy?","land_context":{"mode":"general","lands":[]}}""", encoded)
    }

    @Test
    fun `the transport installs a bounded timeout with the named constants`() {
        val client = answerHttpClient(MockEngine { respond("{}") })
        try {
            // `plugin` throws IllegalStateException when the plugin is not installed, so this call
            // is the installation assertion (Ktor 3.1 does not expose the installed config).
            assertNotNull(client.plugin(HttpTimeout))
        } finally {
            client.close()
        }

        // The named bounds are finite, so a stalled request can never wait forever.
        assertNotEquals(HttpTimeoutConfig.INFINITE_TIMEOUT_MS, REQUEST_TIMEOUT_MILLIS)
        assertNotEquals(HttpTimeoutConfig.INFINITE_TIMEOUT_MS, CONNECT_TIMEOUT_MILLIS)
        assertNotEquals(HttpTimeoutConfig.INFINITE_TIMEOUT_MS, SOCKET_TIMEOUT_MILLIS)
        assertTrue(REQUEST_TIMEOUT_MILLIS in 1L..60_000L)
        assertTrue(CONNECT_TIMEOUT_MILLIS in 1L..60_000L)
        assertTrue(SOCKET_TIMEOUT_MILLIS in 1L..60_000L)
    }

    @Test
    fun `a stalled response fails within the bound instead of hanging`() = runBlocking {
        val engine = MockEngine {
            delay(5_000)
            respond(
                content = answeredFixture,
                status = HttpStatusCode.OK,
                headers = headersOf(HttpHeaders.ContentType, ContentType.Application.Json.toString()),
            )
        }
        val service = KtorAnswerService(
            client = answerHttpClient(engine, requestTimeoutMillis = 200L),
            baseUrl = "https://api.example.invalid/",
        )

        val failure = assertFailsWith<AnswerServiceUnavailableException> {
            service.ask(generalAskRequest(question = "  ¿Puedo regar hoy?  "))
        }
        // The payload-free signal is what reaches the state layer: the Ktor message (which names
        // the endpoint) is deliberately never propagated.
        assertEquals("The answer service could not be reached", failure.message)
    }

    @Test
    fun `an input output failure is reported as unreachable`() = runTest {
        val engine = MockEngine { throw IOException("connection failed") }
        val service = KtorAnswerService(
            client = answerHttpClient(engine),
            baseUrl = "https://api.example.invalid/",
        )

        val failure = assertFailsWith<AnswerServiceUnavailableException> {
            service.ask(generalAskRequest(question = "  ¿Puedo regar hoy?  "))
        }
        assertEquals("The answer service could not be reached", failure.message)
    }

    @Test
    fun `an error status with an answer-shaped body fails and is never an answer`() = runTest {
        val engine = MockEngine {
            respond(
                content = answeredFixture,
                status = HttpStatusCode.InternalServerError,
                headers = headersOf(HttpHeaders.ContentType, ContentType.Application.Json.toString()),
            )
        }
        val service = KtorAnswerService(
            client = answerHttpClient(engine),
            baseUrl = "https://api.example.invalid/",
        )

        val failure = assertFailsWith<AnswerServiceErrorException> {
            service.ask(generalAskRequest(question = "  ¿Puedo regar hoy?  "))
        }
        assertEquals("The answer service reported a failure", failure.message)
    }

    @Test
    fun `a declared validation failure status is a service error`() = runTest {
        val engine = MockEngine {
            respond(
                content = "{}",
                status = HttpStatusCode.UnprocessableEntity,
                headers = headersOf(HttpHeaders.ContentType, ContentType.Application.Json.toString()),
            )
        }
        val service = KtorAnswerService(
            client = answerHttpClient(engine),
            baseUrl = "https://api.example.invalid/",
        )

        assertFailsWith<AnswerServiceErrorException> {
            service.ask(generalAskRequest(question = "  ¿Puedo regar hoy?  "))
        }
    }

    @Test
    fun `a 200 body that cannot be decoded fails instead of fabricating an answer`() = runTest {
        val engine = MockEngine {
            respond(
                content = """{"status":"answered","answer":"sin cerrar""",
                status = HttpStatusCode.OK,
                headers = headersOf(HttpHeaders.ContentType, ContentType.Application.Json.toString()),
            )
        }
        val service = KtorAnswerService(
            client = answerHttpClient(engine),
            baseUrl = "https://api.example.invalid/",
        )

        assertFailsWith<AnswerServiceErrorException> {
            service.ask(generalAskRequest(question = "  ¿Puedo regar hoy?  "))
        }
    }

    private suspend fun OutgoingContent.asText(): String = when (this) {
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
}
