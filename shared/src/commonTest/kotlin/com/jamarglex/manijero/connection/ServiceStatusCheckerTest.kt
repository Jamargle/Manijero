package com.jamarglex.manijero.connection

import com.jamarglex.manijero.chat.answerHttpClient
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
import io.ktor.http.headersOf
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.yield
import kotlinx.io.IOException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

private const val HEALTH_OK = """{"status":"ok","service":"manijero-backend"}"""
private const val READY = """{"status":"ready","active_campaign":"2026","extra":{"a":1}}"""
private const val UNAVAILABLE = """{"status":"unavailable","reason":"no campaign"}"""
private const val BASE = "http://192.168.1.20:8000"

private typealias Handler = suspend MockRequestHandleScope.(HttpRequestData) -> HttpResponseData

/**
 * The probe's fixed outcome mapping, request shape, and cancellation, against a mock engine with the
 * production client settings (`expectSuccess`, timeouts, content negotiation).
 */
class ServiceStatusCheckerTest {
    private fun MockRequestHandleScope.json(body: String, status: HttpStatusCode = HttpStatusCode.OK) =
        respond(body, status, headersOf(HttpHeaders.ContentType, ContentType.Application.Json.toString()))

    private fun engine(health: Handler, ready: Handler = { json(READY) }) = MockEngine { request ->
        val path = request.url.encodedPath
        when {
            path.endsWith("/health") -> health(request)
            path.endsWith("/ready") -> ready(request)
            else -> respond("", HttpStatusCode.NotFound)
        }
    }

    private suspend fun check(engine: MockEngine, base: String = BASE) =
        KtorServiceStatusChecker(answerHttpClient(engine)).check(base)

    @Test
    fun `a healthy and ready service is ready`() = runTest {
        val engine = engine(health = { json(HEALTH_OK) })
        assertEquals(ServiceCheckResult.Ready, check(engine))
        assertEquals(listOf("/health", "/ready"), engine.requestHistory.map { it.url.encodedPath })
    }

    @Test
    fun `a 503 unavailable readiness is not ready`() = runTest {
        val engine = engine(health = { json(HEALTH_OK) }, ready = { json(UNAVAILABLE, HttpStatusCode.ServiceUnavailable) })
        assertEquals(ServiceCheckResult.NotReady, check(engine))
    }

    @Test
    fun `a failed, erroring or unexpected readiness is unknown`() = runTest {
        listOf<Handler>(
            { throw IOException("reset") },
            { json(READY, HttpStatusCode.InternalServerError) },
            { json(UNAVAILABLE) },
            { json(READY, HttpStatusCode.ServiceUnavailable) },
            { json("<html>proxy</html>") },
            { json("""{"status":"ready"""") },
            { json("""{"status":"maybe"}""") },
        ).forEachIndexed { index, ready ->
            assertEquals(ServiceCheckResult.ReadyUnknown, check(engine({ json(HEALTH_OK) }, ready)), "case $index")
        }
    }

    @Test
    fun `a refused or failed health request is unreachable and readiness is never asked`() = runTest {
        listOf<Handler>(
            { throw IOException("refused") },
            { throw IllegalArgumentException("unresolved address") },
        ).forEach { health ->
            val engine = engine(health)
            assertEquals(ServiceCheckResult.Unreachable, check(engine))
            assertTrue(engine.requestHistory.none { it.url.encodedPath == "/ready" })
        }
    }

    @Test
    fun `a stalled health request times out as unreachable`() = runTest {
        val engine = MockEngine { awaitCancellation() }
        val checker = KtorServiceStatusChecker(answerHttpClient(engine, requestTimeoutMillis = 50L))
        assertEquals(ServiceCheckResult.Unreachable, checker.check(BASE))
    }

    @Test
    fun `something other than the Manijero service is not Manijero and readiness is never asked`() = runTest {
        listOf<Handler>(
            { respond("", HttpStatusCode.NotFound) },
            { json(HEALTH_OK, HttpStatusCode.InternalServerError) },
            { json("""{"status":"ok","service":"other-backend"}""") },
            { json("""{"status":"ok"}""") },
            { json("""{"status":"down","service":"manijero-backend"}""") },
            { json("[1,2,3]") },
            { respond("<html><body>router</body></html>", HttpStatusCode.OK, headersOf(HttpHeaders.ContentType, "text/html")) },
            { respond("", HttpStatusCode.OK) },
        ).forEachIndexed { index, health ->
            val engine = engine(health)
            assertEquals(ServiceCheckResult.NotManijero, check(engine), "case $index")
            assertTrue(engine.requestHistory.none { it.url.encodedPath == "/ready" }, "case $index")
        }
    }

    @Test
    fun `unknown health keys are ignored`() = runTest {
        val engine = engine(health = { json("""{"status":"ok","service":"manijero-backend","version":"1.2"}""") })
        assertEquals(ServiceCheckResult.Ready, check(engine))
    }

    @Test
    fun `probes are bodiless GETs with no token under the base path`() = runTest {
        val engine = engine(health = { json(HEALTH_OK) })
        check(engine, base = "https://qa.example.org/manijero/")

        assertEquals(listOf("/manijero/health", "/manijero/ready"), engine.requestHistory.map { it.url.encodedPath })
        engine.requestHistory.forEach { request ->
            assertEquals(HttpMethod.Get, request.method)
            assertEquals("qa.example.org", request.url.host)
            assertTrue(request.body is OutgoingContent.NoContent, "a probe carries no body")
            assertTrue(request.headers[HttpHeaders.Authorization] == null, "a probe carries no token")
            assertTrue(request.url.parameters.isEmpty(), "a probe carries no query")
        }
    }

    @Test
    fun `cancellation propagates instead of becoming a result`() = runTest {
        val started = CompletableDeferred<Unit>()
        val engine = MockEngine {
            started.complete(Unit)
            awaitCancellation()
        }
        val checker = KtorServiceStatusChecker(answerHttpClient(engine))
        val running = async { checker.check(BASE) }
        started.await()
        yield()
        running.cancel()
        assertFailsWith<CancellationException> { running.await() }
    }
}
