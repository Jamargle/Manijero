package com.jamarglex.manijero.chat

/**
 * The two honest categories a failed `/ask` request can be shown as. The state layer keeps only
 * the reason; the plain-Spanish explanation lives in the shared Compose string resources, so the
 * presentation never depends on a transport type.
 *
 * The app cannot reliably tell "there is no connection" from "the server is down", so neither
 * category claims more than reachability.
 */
enum class RequestFailure {
    /** Timeout, connection, or any other I/O failure: the service could not be reached. */
    COULD_NOT_REACH_SERVICE,

    /** Error status, unusable body, or no service configured: the service itself failed. */
    SERVICE_ERROR,
}

/**
 * Payload-free signal that the request never reached a usable answer service. It deliberately
 * carries no URL, request body, or question text: the underlying Ktor exception may name the
 * endpoint, so it is never rethrown, logged, or shown.
 */
class AnswerServiceUnavailableException : Exception("The answer service could not be reached")

/**
 * Payload-free signal that the service answered with a failure. It deliberately carries no
 * response body, status detail, or question text, because a raw transport message could echo the
 * request or an unusable payload.
 */
class AnswerServiceErrorException : Exception("The answer service reported a failure")
