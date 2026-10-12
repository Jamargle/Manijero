package com.jamarglex.manijero.chat

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.HttpClientEngine
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/** Upper bound declared by the accepted `/ask` contract for `question`. */
const val MAX_QUESTION_LENGTH = 2_000

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
 */
fun answerHttpClient(engine: HttpClientEngine): HttpClient = HttpClient(engine) {
    install(ContentNegotiation) {
        json(answerJson)
    }
}

@Serializable
data class AskRequest(
    val question: String,
    val land_context: LandContext,
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

class KtorAnswerService(
    private val client: HttpClient,
    baseUrl: String,
) : AnswerService {
    private val askUrl = "${baseUrl.trimEnd('/')}/ask"

    override suspend fun ask(request: AskRequest): AskResponse = client.post(askUrl) {
        contentType(ContentType.Application.Json)
        setBody(request)
    }.body()
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
