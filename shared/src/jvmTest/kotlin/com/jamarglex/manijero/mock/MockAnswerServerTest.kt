package com.jamarglex.manijero.mock

import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskRequest
import com.jamarglex.manijero.chat.KtorAnswerService
import com.jamarglex.manijero.chat.LandContext
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.MinimalLandContext
import com.jamarglex.manijero.chat.WaterRegime
import com.jamarglex.manijero.chat.answerHttpClient
import io.ktor.client.request.delete
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.put
import io.ktor.client.request.setBody
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.contentType
import io.ktor.server.testing.ApplicationTestBuilder
import io.ktor.server.testing.testApplication
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

class MockAnswerServerTest {
    private val examples = loadContractExamples(contractExamplesDirectory())
    private val logLines = mutableListOf<String>()

    private fun mockTest(block: suspend ApplicationTestBuilder.() -> Unit) = testApplication {
        application { mockAnswerModule(examples) { line -> logLines += line } }
        block()
    }

    @Test
    fun `health and ready answer with the exact mock payloads`() = mockTest {
        val health = client.get("/health")
        val ready = client.get("/ready")

        assertEquals(HttpStatusCode.OK, health.status)
        assertEquals(HEALTH_BODY, health.bodyAsText())
        assertEquals("""{"status":"ok","service":"manijero-mock"}""", health.bodyAsText())
        assertEquals(HttpStatusCode.OK, ready.status)
        assertEquals("""{"status":"ready","service":"manijero-mock"}""", ready.bodyAsText())
        assertTrue(health.contentType()!!.match(ContentType.Application.Json))
    }

    @Test
    fun `ask answers 200 with a JSON example`() = mockTest {
        val response = client.post("/ask") {
            header(HttpHeaders.ContentType, ContentType.Application.Json.toString())
            setBody("""{"question":"¿Hola?","land_context":{"mode":"general","lands":[]}}""")
        }

        assertEquals(HttpStatusCode.OK, response.status)
        assertTrue(response.contentType()!!.match(ContentType.Application.Json))
        assertTrue(response.bodyAsText().contains("\"status\":\"answered\""))
    }

    @Test
    fun `wrong methods and unknown paths never answer 200`() = mockTest {
        val responses = listOf(
            client.get("/ask"),
            client.put("/ask"),
            client.post("/health"),
            client.delete("/ready"),
            client.get("/otra-ruta"),
        )

        responses.forEach { assertNotEquals(HttpStatusCode.OK, it.status) }
    }

    @Test
    fun `the app's own answer client decodes all three states`() = mockTest {
        val service = KtorAnswerService(answerHttpClient(client.engine), baseUrl = "http://localhost")
        fun ask(mode: LandContextMode, vararg ids: String) = AskRequest(
            question = "¿Qué ayudas hay?",
            land_context = LandContext(mode, ids.map { MinimalLandContext(id = it) }),
        )

        assertEquals(AnswerStatus.answered, service.ask(ask(LandContextMode.general)).status)
        assertEquals(AnswerStatus.abstained, service.ask(ask(LandContextMode.all_active, "una")).status)
        val clarification = service.ask(ask(LandContextMode.all_active, "una", "dos"))
        assertEquals(AnswerStatus.needs_land_clarification, clarification.status)
        assertEquals(listOf("una", "dos"), clarification.land_ids_to_choose)
        val selected = service.ask(ask(LandContextMode.selected, "dos"))
        assertEquals(AnswerStatus.answered, selected.status)
        assertEquals(LandContextMode.selected, selected.land_scope)
    }

    @Test
    fun `invalid requests get fixed generic bodies that echo no request value`() = mockTest {
        val question = "Mi finca 🫒 en Úbeda — ¿plazo?"
        val notJson = client.post("/ask") { setBody("pregunta: $question") }
        val emptyLands = client.post("/ask") {
            header(HttpHeaders.ContentType, ContentType.Application.Json.toString())
            setBody("""{"question":"$question","land_context":{"mode":"selected","lands":[]}}""")
        }
        val duplicate = client.post("/ask") {
            header(HttpHeaders.ContentType, ContentType.Application.Json.toString())
            setBody(
                """{"question":"$question","land_context":{"mode":"all_active","lands":""" +
                    """[{"id":"finca-secreta"},{"id":"finca-secreta"}]}}""",
            )
        }

        assertEquals(HttpStatusCode.BadRequest, notJson.status)
        assertEquals(MALFORMED_BODY, notJson.bodyAsText())
        listOf(emptyLands, duplicate).forEach { response ->
            assertEquals(HttpStatusCode.UnprocessableEntity, response.status)
            assertEquals(CONTRACT_VIOLATION_BODY, response.bodyAsText())
        }
    }

    @Test
    fun `log lines hold only method, path, status, and example file name`() = mockTest {
        val service = KtorAnswerService(answerHttpClient(client.engine), baseUrl = "http://localhost")
        val question = "¿Puedo regar la finca de mi suegra 🫒 hoy?"
        service.ask(
            AskRequest(
                question = question,
                land_context = LandContext(
                    LandContextMode.all_active,
                    listOf(
                        MinimalLandContext(id = "land-secret-1", municipality = "Baeza", water_regime = WaterRegime.irrigated),
                        MinimalLandContext(id = "land-secret-2", municipality = "Jódar"),
                    ),
                ),
            ),
        )
        client.post("/ask") { setBody("not json $question") }
        client.get("/health")
        client.get("/buscar/$question")

        assertEquals(
            listOf(
                "mock-answer-server POST /ask 200 $CLARIFICATION_EXAMPLE_FILE",
                "mock-answer-server POST /ask 400 -",
                "mock-answer-server GET /health 200 -",
                "mock-answer-server GET (other path) 404 -",
            ),
            logLines,
        )
        val joined = logLines.joinToString("\n")
        listOf("regar", "suegra", "land-secret", "Baeza", "Jódar", "irrigated", "buscar").forEach {
            assertFalse(joined.contains(it), "log leaked: $it")
        }
    }

    @Test
    fun `options parse only the three expected flags`() {
        val parsed = parseMockServerOptions(arrayOf("--examples", "contracts/examples", "--host", "127.0.0.1", "--port", "8000"))

        assertEquals(MockServerOptions(java.io.File("contracts/examples"), "127.0.0.1", 8000), parsed)
        assertEquals(null, parseMockServerOptions(arrayOf("--host", "127.0.0.1", "--port", "8000")))
        assertEquals(null, parseMockServerOptions(arrayOf("--examples", "x", "--host", "h", "--port", "0")))
        assertEquals(null, parseMockServerOptions(arrayOf("--examples", "x", "--host", "h", "--port", "70000")))
        assertEquals(null, parseMockServerOptions(arrayOf("--examples", "x", "--host", "h", "--port")))
    }
}
