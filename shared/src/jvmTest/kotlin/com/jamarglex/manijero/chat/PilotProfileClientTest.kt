package com.jamarglex.manijero.chat

import com.jamarglex.manijero.connection.KtorServiceStatusChecker
import com.jamarglex.manijero.connection.ServiceCheckResult
import com.jamarglex.manijero.mock.contractExamplesDirectory
import io.ktor.client.request.get
import io.ktor.client.request.post
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.server.testing.ApplicationTestBuilder
import io.ktor.server.testing.testApplication
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * The app's own answer client against an in-process fake of the pilot profile's `/ask` gate
 * ([FakePilotGuard]), so the scenario 4 table runs without a service, device, or emulator. Fake
 * tokens only.
 */
class PilotProfileClientTest {
    private val answeredFixture = File(contractExamplesDirectory(), "response-answered.json").readText()
    private val issuedToken = "fakeIssuedTokenForTestsOnly-0123456789abcdef"
    private val otherToken = "fakeOtherTokenForTestsOnly-0123456789abcdef"
    private val guard = FakePilotGuard(setOf(issuedToken), allowancePerMinute = 2, answerBody = answeredFixture)

    private fun pilotTest(block: suspend ApplicationTestBuilder.() -> Unit) = testApplication {
        application { with(guard) { module() } }
        block()
    }

    private fun ApplicationTestBuilder.service(token: String?) = KtorAnswerService(
        answerHttpClient(client.engine),
        baseUrl = "http://localhost",
        pilotToken = PilotToken.fromBuildSetting(token),
    )

    @Test
    fun `a build with the issued token gets the answer decoded as today`() = pilotTest {
        val response = service(issuedToken).ask(generalAskRequest("¿Puedo regar hoy?"))

        assertEquals(AnswerStatus.answered, response.status)
        assertTrue(response.sources.isNotEmpty())
    }

    @Test
    fun `a build without a token or with another token gets the service error`() = pilotTest {
        listOf(null, otherToken).forEach { token ->
            val failure = assertFailsWith<AnswerServiceErrorException> {
                service(token).ask(generalAskRequest("¿Puedo regar hoy?"))
            }
            assertFalse(issuedToken in failure.stackTraceToString())
            assertFalse(otherToken in failure.stackTraceToString())
        }
    }

    @Test
    fun `the fake refuses like the pilot guard, with its headers`() = pilotTest {
        val missing = client.post("/ask")
        val wrongScheme = client.post("/ask") { headers.append(HttpHeaders.Authorization, "Basic $issuedToken") }

        listOf(missing, wrongScheme).forEach {
            assertEquals(HttpStatusCode.Unauthorized, it.status)
            assertEquals("Bearer", it.headers[HttpHeaders.WWWAuthenticate])
        }
        repeat(2) {
            client.post("/ask") { headers.append(HttpHeaders.Authorization, "bearer  $issuedToken ") }
        }
        val limited = client.post("/ask") { headers.append(HttpHeaders.Authorization, "Bearer $issuedToken") }
        assertEquals(HttpStatusCode.TooManyRequests, limited.status)
        assertEquals("60", limited.headers[HttpHeaders.RetryAfter])
    }

    @Test
    fun `past the allowance the issued token gets the same service error`() = pilotTest {
        val service = service(issuedToken)
        repeat(2) { service.ask(generalAskRequest("¿Puedo regar hoy?")) }

        val failure = assertFailsWith<AnswerServiceErrorException> {
            service.ask(generalAskRequest("¿Puedo regar hoy?"))
        }
        assertFalse(issuedToken in failure.stackTraceToString())
    }

    @Test
    fun `the connection check is ready without any token`() = pilotTest {
        val result = KtorServiceStatusChecker(answerHttpClient(client.engine)).check("http://localhost")

        assertEquals(ServiceCheckResult.Ready, result)
        assertEquals(listOf("/health" to false, "/ready" to false), guard.authorizationSeenOnPath)
    }

    @Test
    fun `only ask requests ever carry the authorization header`() = pilotTest {
        service(issuedToken).ask(generalAskRequest("¿Puedo regar hoy?"))
        KtorServiceStatusChecker(answerHttpClient(client.engine)).check("http://localhost")
        client.get("/health")

        assertEquals(
            listOf("/ask" to true, "/health" to false, "/ready" to false, "/health" to false),
            guard.authorizationSeenOnPath,
        )
    }
}
