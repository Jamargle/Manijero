package com.jamarglex.manijero.connection

import io.ktor.client.HttpClient
import io.ktor.client.plugins.expectSuccess
import io.ktor.client.request.get
import io.ktor.client.statement.HttpResponse
import io.ktor.client.statement.bodyAsText
import io.ktor.http.HttpStatusCode
import io.ktor.http.isSuccess
import kotlinx.coroutines.CancellationException
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/** The fixed outcomes of one connection check. No status code, body, or exception text is kept. */
enum class ServiceCheckResult {
    /** `/health` is the Manijero answer service and `/ready` says it can answer. */
    Ready,

    /** `/health` is fine, but `/ready` answered 503 `unavailable`. */
    NotReady,

    /** `/health` is fine, but `/ready` failed, timed out, or answered something unexpected. */
    ReadyUnknown,

    /** `/health` could not be reached at all. */
    Unreachable,

    /** Something answered `/health`, but it is not the Manijero answer service. */
    NotManijero,
}

/** Checks whether an answer service at a base URL is reachable and ready. */
fun interface ServiceStatusChecker {
    suspend fun check(baseUrl: String): ServiceCheckResult
}

private val probeJson = Json { ignoreUnknownKeys = true }

/** Only the two fields the client reads from either operational probe. */
@Serializable
private data class ProbeBody(val status: String? = null, val service: String? = null)

private const val MANIJERO_SERVICE_NAME = "manijero-backend"

/**
 * Sends `GET <url>/health` and, only after a valid health body, `GET <url>/ready`, reusing the
 * host's answer client and its timeouts. Neither request carries a body, a question, land data, or
 * a token, and nothing about the address or the outcome is logged. Every failure maps to one
 * [ServiceCheckResult]; a [CancellationException] is rethrown so leaving the screen stops the check.
 */
class KtorServiceStatusChecker(private val client: HttpClient) : ServiceStatusChecker {
    override suspend fun check(baseUrl: String): ServiceCheckResult {
        val base = baseUrl.trimEnd('/')
        val health = probe("$base/health") ?: return ServiceCheckResult.Unreachable
        val healthBody = parse(health.text)
        if (!health.status.isSuccess() ||
            healthBody?.status != "ok" ||
            healthBody.service != MANIJERO_SERVICE_NAME
        ) {
            return ServiceCheckResult.NotManijero
        }

        val ready = probe("$base/ready") ?: return ServiceCheckResult.ReadyUnknown
        val readyStatus = parse(ready.text)?.status
        return when {
            ready.status == HttpStatusCode.OK && readyStatus == "ready" -> ServiceCheckResult.Ready
            ready.status == HttpStatusCode.ServiceUnavailable && readyStatus == "unavailable" ->
                ServiceCheckResult.NotReady
            else -> ServiceCheckResult.ReadyUnknown
        }
    }

    private class ProbeResponse(val status: HttpStatusCode, val text: String?)

    /** One bodiless GET; `null` when no response arrived (refused, timed out, or any I/O failure). */
    private suspend fun probe(url: String): ProbeResponse? = try {
        val response: HttpResponse = client.get(url) { expectSuccess = false }
        ProbeResponse(response.status, runCatchingNonCancellation { response.bodyAsText() })
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (_: Exception) {
        null
    }

    private fun parse(text: String?): ProbeBody? =
        text?.let { runCatching { probeJson.decodeFromString(ProbeBody.serializer(), it) }.getOrNull() }

    private suspend fun runCatchingNonCancellation(block: suspend () -> String): String? = try {
        block()
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (_: Exception) {
        null
    }
}
