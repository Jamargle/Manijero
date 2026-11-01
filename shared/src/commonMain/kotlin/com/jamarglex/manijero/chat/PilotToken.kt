package com.jamarglex.manijero.chat

import io.ktor.http.URLProtocol
import io.ktor.http.Url

/** Shortest pilot token the service accepts (`backend/README.md`, credential rotation). */
const val PILOT_TOKEN_MIN_LENGTH = 32

/** Longest pilot token a build accepts; anything longer is not a token the owner was given. */
const val PILOT_TOKEN_MAX_LENGTH = 512

/** The RFC 6750 `b64token` shape: unreserved and base64 characters, then optional `=` padding. */
private val PILOT_TOKEN_SHAPE = Regex("^[A-Za-z0-9._~+/-]+=*$")

/**
 * The per-client pilot bearer token built into a test app (`client_pilot_credentials`).
 *
 * It is not a data class, so no generated `toString`, `copy`, or component can expose the value:
 * [toString] is always `PilotToken(redacted)`, and only the shared answer transport reads the
 * value, to build one `Authorization` header. It is never shown, logged, or put in state.
 */
class PilotToken private constructor(private val value: String) {
    /** The `Authorization` header value for one `/ask` request. */
    internal fun bearerHeaderValue(): String = "Bearer $value"

    override fun toString(): String = "PilotToken(redacted)"

    companion object {
        /**
         * The token from the build setting, or `null` when none is configured or the value is not
         * a pilot token, so a tampered or malformed build sends nothing instead of a wrong header.
         */
        fun fromBuildSetting(raw: String?): PilotToken? {
            if (raw.isNullOrBlank()) return null
            if (raw.length !in PILOT_TOKEN_MIN_LENGTH..PILOT_TOKEN_MAX_LENGTH) return null
            if (!PILOT_TOKEN_SHAPE.matches(raw)) return null
            return PilotToken(raw)
        }
    }
}

/** Loopback addresses a development service can listen on, including the Android emulator's host. */
private val LOOPBACK_HOSTS = setOf("localhost", "127.0.0.1", "::1", "[::1]", "10.0.2.2")

/**
 * Whether a request to [url] may carry the pilot token: only over `https`, or over `http` to this
 * computer (or the emulator's view of it). Cleartext to any other host, such as a LAN address set
 * in `Conexión`, never carries it.
 */
fun mayCarryPilotToken(url: Url): Boolean = when (url.protocol) {
    URLProtocol.HTTPS -> true
    URLProtocol.HTTP -> url.host.lowercase() in LOOPBACK_HOSTS
    else -> false
}
