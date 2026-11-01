package com.jamarglex.manijero.chat

import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.server.application.Application
import io.ktor.server.application.ApplicationCall
import io.ktor.server.request.path
import io.ktor.server.response.header
import io.ktor.server.response.respondText
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import io.ktor.server.routing.routing

/**
 * In-process stand-in for the pilot profile of the answer service, mirroring
 * `backend/app/pilot_guard.py`: only `/ask` is gated; a missing or unknown bearer token gets `401`
 * with `WWW-Authenticate: Bearer`; past the per-client allowance a known token gets `429` with
 * `Retry-After: 60`. `/health` and `/ready` stay open. The scheme is matched case-insensitively and
 * the token is stripped, like `_bearer_token`.
 *
 * It records, per path, whether a request carried an `Authorization` header, never its value.
 */
class FakePilotGuard(
    private val validTokens: Set<String>,
    private val allowancePerMinute: Int,
    private val answerBody: String,
) {
    private val acceptedPerToken = mutableMapOf<String, Int>()
    val authorizationSeenOnPath = mutableListOf<Pair<String, Boolean>>()

    fun Application.module() {
        routing {
            get("/health") {
                record(call)
                call.respondJson(HttpStatusCode.OK, """{"status":"ok","service":"manijero-backend"}""")
            }
            get("/ready") {
                record(call)
                call.respondJson(HttpStatusCode.OK, """{"status":"ready","service":"manijero-backend"}""")
            }
            post("/ask") {
                record(call)
                val token = bearerToken(call.request.headers[HttpHeaders.Authorization])
                when {
                    token == null || token !in validTokens -> {
                        call.response.header(HttpHeaders.WWWAuthenticate, "Bearer")
                        call.respondJson(HttpStatusCode.Unauthorized, """{"detail":"Client credentials are required."}""")
                    }
                    (acceptedPerToken[token] ?: 0) >= allowancePerMinute -> {
                        call.response.header(HttpHeaders.RetryAfter, "60")
                        call.respondJson(HttpStatusCode.TooManyRequests, """{"detail":"Too many requests."}""")
                    }
                    else -> {
                        acceptedPerToken[token] = (acceptedPerToken[token] ?: 0) + 1
                        call.respondJson(HttpStatusCode.OK, answerBody)
                    }
                }
            }
        }
    }

    private fun record(call: ApplicationCall) {
        authorizationSeenOnPath += call.request.path() to (call.request.headers[HttpHeaders.Authorization] != null)
    }

    private fun bearerToken(header: String?): String? {
        val parts = header?.trim()?.split(' ', limit = 2) ?: return null
        if (parts.size != 2 || !parts[0].equals("bearer", ignoreCase = true)) return null
        return parts[1].trim().ifEmpty { null }
    }

    private suspend fun ApplicationCall.respondJson(status: HttpStatusCode, body: String) =
        respondText(body, ContentType.Application.Json, status)
}
