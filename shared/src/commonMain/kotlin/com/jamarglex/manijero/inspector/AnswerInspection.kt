package com.jamarglex.manijero.inspector

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull

/**
 * The development-only `inspection` object of `/ask` (`answer-inspection-v1`): ids, scores, fixed
 * codes, timings, and public corpus text. It lives in memory with the transcript entry and is never
 * persisted, logged, exported, or shared.
 */
@Serializable
data class AnswerInspection(
    val schema: String,
    val retrieval: InspectionRetrieval? = null,
    val drafting: InspectionDrafting? = null,
    val verification: InspectionVerification? = null,
    val outcome: InspectionOutcome,
    val total_ms: Long,
)

@Serializable
data class InspectionRetrieval(
    val mode: String,
    val k: Int,
    val search_calls: Int,
    val duration_ms: Long,
    val vector: InspectionVector? = null,
    val passages: List<InspectionPassage>,
)

@Serializable
data class InspectionVector(val used: Boolean, val fallback_code: String? = null)

@Serializable
data class InspectionPassage(
    val rank: Int,
    val passage_id: String,
    val source_id: String,
    val title: String,
    val location: String,
    val score: Double,
    val lexical_rank: Int? = null,
    val lexical_score: Double? = null,
    val vector_similarity: Double? = null,
    val cited: Boolean,
    val excerpt: String,
)

@Serializable
data class InspectionDrafting(
    val provider: String? = null,
    val outcome: String? = null,
    val status: String? = null,
    val cited_markers: List<Int> = emptyList(),
    val duration_ms: Long? = null,
)

@Serializable
data class InspectionVerification(
    val ok: Boolean,
    val issues: List<String>,
    val claims: List<InspectionClaim>,
    val duration_ms: Long? = null,
)

@Serializable
data class InspectionClaim(
    val index: Int,
    val markers: List<Int>,
    val ok: Boolean,
    val issues: List<String>,
)

@Serializable
data class InspectionOutcome(
    val abstention_reason: String? = null,
    val generation_reason: String? = null,
    val cited_passage_ids: List<String>,
)

const val INSPECTION_SCHEMA = "answer-inspection-v1"
const val MAX_INSPECTION_PASSAGES = 20
const val MAX_INSPECTION_EXCERPT = 2_000
private const val MAX_INSPECTION_TEXT = 400
private const val MAX_INSPECTION_ITEMS = 50

/** Strict on shape (an unknown key or wrong type fails) so a malformed object is dropped whole. */
private val inspectionJson = Json { ignoreUnknownKeys = false }

/**
 * Decodes the raw `inspection` value, or returns `null` for an absent, `null`, malformed, or
 * oversize object. It never throws, so a bad inspection can never turn an answer into a failure.
 */
fun decodeInspectionOrNull(raw: JsonElement?): AnswerInspection? {
    if (raw == null || raw is JsonNull) return null
    val decoded = try {
        inspectionJson.decodeFromJsonElement(AnswerInspection.serializer(), raw)
    } catch (_: Exception) {
        return null
    }
    return decoded.takeIf { it.isWithinBounds() }
}

private fun AnswerInspection.isWithinBounds(): Boolean {
    if (schema != INSPECTION_SCHEMA) return false
    val passages = retrieval?.passages.orEmpty()
    if (passages.size > MAX_INSPECTION_PASSAGES) return false
    if (passages.any { it.excerpt.length > MAX_INSPECTION_EXCERPT }) return false
    val shortTexts = passages.flatMap { listOf(it.passage_id, it.source_id, it.title, it.location) }
    if (shortTexts.any { it.length > MAX_INSPECTION_TEXT }) return false
    val claims = verification?.claims.orEmpty()
    if (claims.size > MAX_INSPECTION_ITEMS) return false
    val codes = verification?.issues.orEmpty() + claims.flatMap { it.issues }
    if (codes.size > MAX_INSPECTION_ITEMS * 4 || codes.any { it.length > MAX_INSPECTION_TEXT }) return false
    return outcome.cited_passage_ids.size <= MAX_INSPECTION_ITEMS
}
