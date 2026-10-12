package com.jamarglex.manijero.chat

import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpMethod
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.OutgoingContent
import io.ktor.http.content.TextContent
import io.ktor.http.headersOf
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Transport-level checks: the accepted contract example is the response body, and the
 * captured outbound request must be exactly one general `POST /ask`.
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
