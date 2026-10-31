package com.jamarglex.manijero.mock

import com.jamarglex.manijero.chat.AskRequest
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.MAX_QUESTION_LENGTH
import com.jamarglex.manijero.chat.answerJson
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.Json

/** Contract bounds from `contracts/openapi.yaml` that the client DTOs do not enforce themselves. */
private const val MAX_LAND_ID_LENGTH = 128
private const val MAX_MUNICIPALITY_LENGTH = 160

/** Outcome of checking one `/ask` body against the contract. */
sealed interface AskValidation {
    data class Valid(val request: AskRequest) : AskValidation

    /** The body is not JSON at all: `400`. */
    data object Malformed : AskValidation

    /** The body is JSON but breaks the `AskRequest` contract: `422`. */
    data object ContractViolation : AskValidation
}

/**
 * Decodes [body] exactly as the client encodes it ([answerJson], unknown keys rejected) and applies
 * the contract rules the DTOs cannot express. Lengths count Unicode code points, like the backend.
 * The result never carries any request value back out on failure.
 */
fun validateAskBody(body: String): AskValidation {
    val element = try {
        Json.parseToJsonElement(body)
    } catch (_: Exception) {
        return AskValidation.Malformed
    }
    // The tree parser tolerates bare words such as `hola`; strict JSON does not.
    if (element.containsBareWord()) return AskValidation.Malformed
    // The contract declares no nullable field; `explicitNulls = false` would otherwise accept them.
    if (element.containsNull()) return AskValidation.ContractViolation
    // The decoder accepts a quoted "true" for a Boolean; the contract (and the backend) do not.
    if (element.hasQuotedRetentionFlag()) return AskValidation.ContractViolation
    val request = try {
        answerJson.decodeFromJsonElement(AskRequest.serializer(), element)
    } catch (_: Exception) {
        return AskValidation.ContractViolation
    }
    return if (request.meetsContract()) AskValidation.Valid(request) else AskValidation.ContractViolation
}

/**
 * Picks the committed example for a valid request. The only changes to an example are the two the
 * accepted backend makes: clarification offers the request's own land IDs in request order, and a
 * `selected` answer reports `land_scope = selected`. `retain_for_improvement` never matters.
 */
fun selectExample(request: AskRequest, examples: ContractExamples): ServedExample {
    val lands = request.land_context.lands
    return when (request.land_context.mode) {
        LandContextMode.general -> examples.answered
        LandContextMode.all_active ->
            if (lands.size <= 1) {
                examples.abstained
            } else {
                examples.clarification.copy(
                    response = examples.clarification.response.copy(land_ids_to_choose = lands.map { it.id }),
                )
            }
        LandContextMode.selected -> examples.answered.copy(
            response = examples.answered.response.copy(land_scope = LandContextMode.selected),
        )
    }
}

private fun AskRequest.meetsContract(): Boolean {
    if (question.codePointLength() !in 1..MAX_QUESTION_LENGTH) return false
    val lands = land_context.lands
    val landsAllowed = when (land_context.mode) {
        LandContextMode.general -> lands.isEmpty()
        LandContextMode.all_active, LandContextMode.selected -> lands.isNotEmpty()
    }
    if (!landsAllowed) return false
    if (lands.map { it.id }.toSet().size != lands.size) return false
    return lands.all { land ->
        land.id.codePointLength() in 1..MAX_LAND_ID_LENGTH &&
            (land.municipality?.let { it.codePointLength() in 1..MAX_MUNICIPALITY_LENGTH } ?: true)
    }
}

private fun String.codePointLength(): Int = codePointCount(0, length)

private fun JsonElement.hasQuotedRetentionFlag(): Boolean =
    ((this as? JsonObject)?.get("retain_for_improvement") as? JsonPrimitive)?.isString == true

private val jsonNumber = Regex("""-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?""")

private fun JsonElement.containsBareWord(): Boolean = when (this) {
    is JsonObject -> values.any { it.containsBareWord() }
    is JsonArray -> any { it.containsBareWord() }
    is JsonPrimitive -> !isString && content != "true" && content != "false" && content != "null" &&
        !jsonNumber.matches(content)
}

private fun JsonElement.containsNull(): Boolean = when (this) {
    is JsonNull -> true
    is JsonObject -> values.any { it.containsNull() }
    is JsonArray -> any { it.containsNull() }
    else -> false
}
