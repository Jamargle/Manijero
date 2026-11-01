package com.jamarglex.manijero.connection

import kotlin.concurrent.Volatile

/** The longest answer-service address a tester may type, after trimming. */
const val MAX_SERVICE_ADDRESS_LENGTH = 512

private const val MAX_PORT = 65_535

/** The outcome of [normalizeServiceAddress]: a usable base URL, or a refusal with no detail. */
sealed interface ServiceAddressInput {
    data class Valid(val url: String) : ServiceAddressInput
    data object Invalid : ServiceAddressInput
}

/**
 * Turns what a tester typed into an answer-service base URL, or refuses it.
 *
 * Surrounding spaces and trailing `/` are removed first. The address must then be at most
 * [MAX_SERVICE_ADDRESS_LENGTH] characters, use `http` or `https`, name an ASCII host (a name, an
 * IPv4 address, or a bracketed IPv6 address), and may carry a port from 1 to 65535 and a path
 * prefix. User info, a query, a fragment, spaces, and non-ASCII characters are refused. The scheme
 * and host are lowercased; the path keeps its case.
 */
fun normalizeServiceAddress(input: String): ServiceAddressInput {
    val trimmed = input.trim().trimEnd('/')
    if (trimmed.isEmpty() || trimmed.length > MAX_SERVICE_ADDRESS_LENGTH) return ServiceAddressInput.Invalid
    if (trimmed.any { it.code !in 0x21..0x7E }) return ServiceAddressInput.Invalid

    val schemeEnd = trimmed.indexOf("://")
    if (schemeEnd <= 0) return ServiceAddressInput.Invalid
    val scheme = trimmed.substring(0, schemeEnd).lowercase()
    if (scheme != "http" && scheme != "https") return ServiceAddressInput.Invalid

    val rest = trimmed.substring(schemeEnd + 3)
    if ('?' in rest || '#' in rest || '\\' in rest) return ServiceAddressInput.Invalid
    val pathStart = rest.indexOf('/').let { if (it < 0) rest.length else it }
    val authority = rest.substring(0, pathStart)
    val path = rest.substring(pathStart)
    if ('@' in authority) return ServiceAddressInput.Invalid

    val hostAndPort = splitHostAndPort(authority) ?: return ServiceAddressInput.Invalid
    val (host, port) = hostAndPort
    val portSuffix = if (port == null) "" else ":$port"
    return ServiceAddressInput.Valid("$scheme://${host.lowercase()}$portSuffix$path")
}

/** Splits `host[:port]` or `[ipv6][:port]`; `null` when either part is malformed. */
private fun splitHostAndPort(authority: String): Pair<String, Int?>? {
    val host: String
    val portText: String?
    if (authority.startsWith("[")) {
        val close = authority.indexOf(']')
        if (close < 0) return null
        val literal = authority.substring(1, close)
        if (literal.isEmpty() || literal.any { !it.isHexDigit() && it != ':' && it != '.' }) return null
        host = authority.substring(0, close + 1)
        val after = authority.substring(close + 1)
        portText = when {
            after.isEmpty() -> null
            after.startsWith(":") -> after.substring(1)
            else -> return null
        }
    } else {
        val parts = authority.split(':')
        if (parts.size > 2) return null
        host = parts[0]
        portText = parts.getOrNull(1)
        if (host.isEmpty() || host.any { !it.isAsciiLetterOrDigit() && it != '-' && it != '.' }) return null
        if (host.startsWith('.') || host.startsWith('-')) return null
    }
    val port = portText?.let { text ->
        if (text.isEmpty() || text.length > 5 || text.any { it !in '0'..'9' }) return null
        text.toInt().takeIf { it in 1..MAX_PORT } ?: return null
    }
    return host to port
}

private fun Char.isAsciiLetterOrDigit(): Boolean = this in 'a'..'z' || this in 'A'..'Z' || this in '0'..'9'

private fun Char.isHexDigit(): Boolean = this in '0'..'9' || this in 'a'..'f' || this in 'A'..'F'

/**
 * The device store for the one remembered answer-service address. Every method may throw when the
 * platform refuses the read or write; callers treat a throw as "not stored".
 */
interface ServiceAddressStore {
    fun load(): String?
    fun save(address: String)
    fun clear()
}

/** Where the address in use comes from, so the screen can say it in plain words. */
enum class ServiceAddressSource { Default, Saved }

/**
 * The answer-service address a test build uses right now: the saved, still-valid address, or else
 * the build default from `selectAskBaseUrl`. An unreadable or invalid stored value falls back to the
 * default. The value is held in memory after each successful [save] or [reset], and a refused write
 * leaves it unchanged. [current] is read on every `/ask`, so a change applies to the next question.
 */
class ActiveServiceAddress(
    val defaultUrl: String,
    private val store: ServiceAddressStore,
) {
    private data class Resolved(val url: String, val source: ServiceAddressSource)

    @Volatile
    private var resolved: Resolved = initialValue()

    val current: String get() = resolved.url

    val source: ServiceAddressSource get() = resolved.source

    /** Saves an already-normalized [url]; `false` when the store refused it. */
    fun save(url: String): Boolean {
        val stored = runCatching { store.save(url) }.isSuccess
        if (stored) resolved = Resolved(url, ServiceAddressSource.Saved)
        return stored
    }

    /** Forgets the saved address; `false` when the store refused it. */
    fun reset(): Boolean {
        val cleared = runCatching { store.clear() }.isSuccess
        if (cleared) resolved = Resolved(defaultUrl, ServiceAddressSource.Default)
        return cleared
    }

    private fun initialValue(): Resolved {
        val saved = runCatching { store.load() }.getOrNull()
        val valid = saved?.let { normalizeServiceAddress(it) as? ServiceAddressInput.Valid }
        return if (valid != null) {
            Resolved(valid.url, ServiceAddressSource.Saved)
        } else {
            Resolved(defaultUrl, ServiceAddressSource.Default)
        }
    }
}
