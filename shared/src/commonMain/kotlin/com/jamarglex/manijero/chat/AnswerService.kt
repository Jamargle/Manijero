package com.jamarglex.manijero.chat

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.HttpClientEngine
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.ResponseException
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.ContentConvertException
import io.ktor.serialization.kotlinx.json.json
import kotlinx.coroutines.CancellationException
import kotlinx.io.IOException
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.SerializationException
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/** Upper bound declared by the accepted `/ask` contract for `question`. */
const val MAX_QUESTION_LENGTH = 2_000

/**
 * Bounded request timeout. A retrieval-backed answer can be slow, but no request may hang forever:
 * today a stall would leave the composer saying "Estoy preparando la respuesta…" indefinitely.
 */
const val REQUEST_TIMEOUT_MILLIS = 15_000L

/** Bounded connect timeout: an unreachable host must fail instead of waiting for the OS. */
const val CONNECT_TIMEOUT_MILLIS = 10_000L

/** Bounded socket timeout: a connection that stops delivering data is a failure, not a wait. */
const val SOCKET_TIMEOUT_MILLIS = 15_000L

/**
 * JSON settings shared by the answer transport. `explicitNulls = false` keeps unknown
 * optional land attributes out of the payload instead of sending `null` values that the
 * contract does not declare.
 */
@OptIn(ExperimentalSerializationApi::class)
val answerJson: Json = Json {
    explicitNulls = false
}

/**
 * Builds the answer transport from a platform-provided engine, so engines and endpoint
 * configuration stay in platform source sets while the request/response contract stays
 * shared.
 *
 * `expectSuccess = true` makes any non-2xx `/ask` a failure, so an error response can never be
 * decoded into an answer. [requestTimeoutMillis] is a parameter only so tests can install a tiny
 * bound; production uses the named constant.
 */
fun answerHttpClient(
    engine: HttpClientEngine,
    requestTimeoutMillis: Long = REQUEST_TIMEOUT_MILLIS,
): HttpClient = HttpClient(engine) {
    expectSuccess = true
    install(ContentNegotiation) {
        json(answerJson)
    }
    install(HttpTimeout) {
        this.requestTimeoutMillis = requestTimeoutMillis
        connectTimeoutMillis = CONNECT_TIMEOUT_MILLIS
        socketTimeoutMillis = SOCKET_TIMEOUT_MILLIS
    }
}

/**
 * [retain_for_improvement] is the explicit, per-question permission to keep the redacted question
 * and answer for product improvement. It defaults to `false`, and `answerJson` does not encode
 * defaults, so a question without permission sends no retention key at all.
 */
@Serializable
data class AskRequest(
    val question: String,
    val land_context: LandContext,
    val retain_for_improvement: Boolean = false,
)

@Serializable
data class LandContext(
    val mode: LandContextMode,
    val lands: List<MinimalLandContext>,
)

@Serializable
enum class LandContextMode { general, all_active, selected }

@Serializable
data class MinimalLandContext(
    val id: String,
    val municipality: String? = null,
    val water_regime: WaterRegime? = null,
    val production_method: ProductionMethod? = null,
)

@Serializable
enum class WaterRegime { dryland, irrigated, mixed, unknown }

@Serializable
enum class ProductionMethod { conventional, organic, mixed, unknown }

@Serializable
data class AskResponse(
    val status: AnswerStatus,
    val answer: String,
    val sources: List<AnswerSource>,
    val land_scope: LandContextMode,
    val land_ids_to_choose: List<String>,
)

@Serializable
enum class AnswerStatus { answered, abstained, needs_land_clarification }

@Serializable
data class AnswerSource(
    val title: String,
    val issuing_body: String,
    val url: String,
    val location: String,
    val published_or_updated_on: String,
    val verified_on: String,
    val excerpt: String,
)

/** Narrow boundary for a single general question. It never exposes land names or notes. */
interface AnswerService {
    suspend fun ask(request: AskRequest): AskResponse
}

/**
 * Contract client for a single general question. Every thrown transport failure is translated into
 * one of the two payload-free signals, so the presentation layer never has to know Ktor types and
 * no URL, response body, or question text can escape through an exception message.
 *
 * [baseUrl] is read on every [ask], so a test build's `Conexión` address applies to the next
 * question without a restart. Release wiring uses the fixed-[String] constructor.
 */
class KtorAnswerService(
    private val client: HttpClient,
    private val baseUrl: () -> String,
) : AnswerService {
    constructor(client: HttpClient, baseUrl: String) : this(client, { baseUrl })

    override suspend fun ask(request: AskRequest): AskResponse = try {
        client.post("${baseUrl().trimEnd('/')}/ask") {
            contentType(ContentType.Application.Json)
            setBody(request)
        }.body()
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (_: ResponseException) {
        // `expectSuccess`: a 4xx/5xx response is a service failure, never an answer.
        throw AnswerServiceErrorException()
    } catch (_: ContentConvertException) {
        // A 2xx body that cannot be decoded into AskResponse is not an answer either.
        throw AnswerServiceErrorException()
    } catch (_: SerializationException) {
        // Any other serialization failure is the same kind of unusable response.
        throw AnswerServiceErrorException()
    } catch (_: IOException) {
        // Timeout, refused connection, or any other I/O failure: the service was not reached.
        throw AnswerServiceUnavailableException()
    }
}

/** Default app wiring deliberately has no answer endpoint until the backend provides `/ask`. */
object UnavailableAnswerService : AnswerService {
    override suspend fun ask(request: AskRequest): AskResponse =
        error("No answer service has been configured")
}

fun generalAskRequest(question: String) = AskRequest(
    question = question,
    land_context = LandContext(mode = LandContextMode.general, lands = emptyList()),
)
