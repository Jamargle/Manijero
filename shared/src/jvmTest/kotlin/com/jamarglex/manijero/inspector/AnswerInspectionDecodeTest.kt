package com.jamarglex.manijero.inspector

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

/** `decodeInspectionOrNull` returns the model or `null`; it never throws, whatever the payload. */
class AnswerInspectionDecodeTest {
    private fun passage(rank: Int = 1, excerpt: String = "E") =
        """{"rank":$rank,"passage_id":"p$rank","source_id":"s","title":"T","location":"L","score":1.5,""" +
            """"lexical_rank":1,"lexical_score":1.5,"vector_similarity":null,"cited":true,"excerpt":"$excerpt"}"""

    private fun payload(
        passages: String = passage(),
        extra: String = "",
        total: String = "4",
        schema: String = "answer-inspection-v1",
    ) =
        """{"schema":"$schema","retrieval":{"mode":"bm25","k":5,"search_calls":1,"duration_ms":2,""" +
            """"vector":null,"passages":[$passages]},"drafting":null,""" +
            """"verification":{"ok":true,"issues":[],"claims":[],"duration_ms":0},""" +
            """"outcome":{"abstention_reason":null,"generation_reason":null,"cited_passage_ids":["p1"]},""" +
            """"total_ms":$total$extra}"""

    private fun decode(text: String) = decodeInspectionOrNull(Json.parseToJsonElement(text))

    @Test
    fun `a valid payload decodes with null stages kept null`() {
        val decoded = assertNotNull(decode(payload()))

        assertEquals("answer-inspection-v1", decoded.schema)
        assertNull(decoded.drafting)
        assertEquals("p1", decoded.retrieval?.passages?.single()?.passage_id)
        assertEquals(listOf("p1"), decoded.outcome.cited_passage_ids)
    }

    @Test
    fun `an unknown key, a wrong type, or another schema is dropped whole`() {
        assertNull(decode(payload(extra = ""","surprise":1""")))
        assertNull(decode(payload(total = "[4]")))
        assertNull(decode(payload(schema = "answer-inspection-v2")))
        assertNull(decode("""{"schema":"answer-inspection-v1"}"""))
    }

    @Test
    fun `an oversize excerpt or too many passages is dropped`() {
        assertNull(decode(payload(passages = passage(excerpt = "x".repeat(MAX_INSPECTION_EXCERPT + 1)))))
        assertNotNull(decode(payload(passages = passage(excerpt = "x".repeat(MAX_INSPECTION_EXCERPT)))))
        val many = (1..MAX_INSPECTION_PASSAGES + 1).joinToString(",") { passage(rank = it) }
        assertNull(decode(payload(passages = many)))
    }

    @Test
    fun `an absent, null, or non-object value is null and never throws`() {
        assertNull(decodeInspectionOrNull(null))
        assertNull(decodeInspectionOrNull(JsonNull))
        assertNull(decode("\"text\""))
        assertNull(decode("[]"))
        assertNull(decode("7"))
    }
}
