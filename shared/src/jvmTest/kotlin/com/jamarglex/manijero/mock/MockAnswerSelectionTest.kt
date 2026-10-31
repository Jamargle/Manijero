package com.jamarglex.manijero.mock

import com.jamarglex.manijero.chat.AskRequest
import com.jamarglex.manijero.chat.LandContext
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.MinimalLandContext
import com.jamarglex.manijero.chat.answerJson
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

class MockAnswerSelectionTest {
    private val examples = loadContractExamples(contractExamplesDirectory())

    // --- Selection (scenario 9) ---

    @Test
    fun `general serves the answered example unchanged`() {
        val served = selectExample(request(LandContextMode.general), examples)

        assertEquals(examples.answered, served)
    }

    @Test
    fun `all active with one land serves the abstained example unchanged`() {
        val served = selectExample(request(LandContextMode.all_active, "solo"), examples)

        assertEquals(examples.abstained, served)
    }

    @Test
    fun `all active with several lands offers the request's own ids in request order`() {
        val served = selectExample(request(LandContextMode.all_active, "zeta", "alfa", "medio"), examples)

        assertEquals(CLARIFICATION_EXAMPLE_FILE, served.fileName)
        assertEquals(listOf("zeta", "alfa", "medio"), served.response.land_ids_to_choose)
        assertEquals(
            examples.clarification.response.copy(land_ids_to_choose = listOf("zeta", "alfa", "medio")),
            served.response,
        )
    }

    @Test
    fun `selected serves the answered example with selected land scope only`() {
        val served = selectExample(request(LandContextMode.selected, "land-001"), examples)

        assertEquals(ANSWERED_EXAMPLE_FILE, served.fileName)
        assertEquals(examples.answered.response.copy(land_scope = LandContextMode.selected), served.response)
    }

    @Test
    fun `retention permission never changes the served example`() {
        listOf(
            request(LandContextMode.general),
            request(LandContextMode.all_active, "a"),
            request(LandContextMode.all_active, "a", "b"),
            request(LandContextMode.selected, "a"),
        ).forEach { plain ->
            assertEquals(
                selectExample(plain, examples),
                selectExample(plain.copy(retain_for_improvement = true), examples),
            )
        }
    }

    @Test
    fun `the committed request examples select the expected states`() {
        val directory = contractExamplesDirectory()
        fun servedFor(name: String) = selectExample(
            assertIs<AskValidation.Valid>(validateAskBody(File(directory, name).readText())).request,
            examples,
        )

        assertEquals(ANSWERED_EXAMPLE_FILE, servedFor("ask-request-general.json").fileName)
        assertEquals(ANSWERED_EXAMPLE_FILE, servedFor("ask-request-retention-opt-in.json").fileName)
        assertEquals(CLARIFICATION_EXAMPLE_FILE, servedFor("ask-request-all-lands.json").fileName)
    }

    // --- Validation (scenario 10) ---

    @Test
    fun `a valid client-encoded request decodes back to the same request`() {
        val sent = request(LandContextMode.selected, "land-001").copy(
            land_context = LandContext(
                mode = LandContextMode.selected,
                lands = listOf(MinimalLandContext(id = "land-001", municipality = "Úbeda")),
            ),
        )

        val validation = validateAskBody(answerJson.encodeToString(AskRequest.serializer(), sent))

        assertEquals(AskValidation.Valid(sent), validation)
    }

    @Test
    fun `a body that is not JSON is malformed`() {
        listOf(
            "",
            "not json",
            "xx",
            "{\"question\":",
            "{'question': 'x'}",
            """{"question":hola,"land_context":{"mode":"general","lands":[]}}""",
        ).forEach { body ->
            assertEquals(AskValidation.Malformed, validateAskBody(body), "body: $body")
        }
    }

    @Test
    fun `JSON that breaks the contract is a contract violation`() {
        val longQuestion = "a".repeat(2_001)
        val bodies = listOf(
            "[]",
            "\"pregunta\"",
            """{"land_context":{"mode":"general","lands":[]}}""",
            """{"question":"¿Hola?"}""",
            """{"question":"¿Hola?","land_context":{"mode":"general","lands":[]},"extra":1}""",
            """{"question":"¿Hola?","land_context":{"mode":"general","lands":[],"extra":1}}""",
            """{"question":"¿Hola?","land_context":{"mode":"todas","lands":[]}}""",
            """{"question":"","land_context":{"mode":"general","lands":[]}}""",
            """{"question":"$longQuestion","land_context":{"mode":"general","lands":[]}}""",
            """{"question":123,"land_context":{"mode":"general","lands":[]}}""",
            """{"question":"¿Hola?","land_context":{"mode":"general","lands":[]},"retain_for_improvement":"true"}""",
            """{"question":"¿Hola?","land_context":{"mode":"general","lands":[{"id":"a"}]}}""",
            """{"question":"¿Hola?","land_context":{"mode":"all_active","lands":[]}}""",
            """{"question":"¿Hola?","land_context":{"mode":"selected","lands":[]}}""",
            """{"question":"¿Hola?","land_context":{"mode":"all_active","lands":[{"id":"a"},{"id":"a"}]}}""",
            """{"question":"¿Hola?","land_context":{"mode":"selected","lands":[{"id":""}]}}""",
            """{"question":"¿Hola?","land_context":{"mode":"selected","lands":[{"id":"${"x".repeat(129)}"}]}}""",
            """{"question":"¿Hola?","land_context":{"mode":"selected","lands":[{"id":"a","municipality":""}]}}""",
            """{"question":"¿Hola?","land_context":{"mode":"selected","lands":[{"id":"a","water_regime":"wet"}]}}""",
            """{"question":"¿Hola?","land_context":{"mode":"selected","lands":[{"id":"a","name":"Finca"}]}}""",
            """{"question":"¿Hola?","land_context":{"mode":"selected","lands":[{"id":"a","municipality":null}]}}""",
        )
        bodies.forEach { body ->
            assertEquals(AskValidation.ContractViolation, validateAskBody(body), "body: ${body.take(120)}")
        }
    }

    @Test
    fun `question length counts code points so 2000 emoji are accepted and 2001 are not`() {
        val emoji = "🫒"
        fun body(question: String) = """{"question":"$question","land_context":{"mode":"general","lands":[]}}"""

        assertIs<AskValidation.Valid>(validateAskBody(body(emoji.repeat(2_000))))
        assertEquals(AskValidation.ContractViolation, validateAskBody(body(emoji.repeat(2_001))))
    }

    private fun request(mode: LandContextMode, vararg ids: String) = AskRequest(
        question = "¿Qué ayudas hay?",
        land_context = LandContext(mode = mode, lands = ids.map { MinimalLandContext(id = it) }),
    )
}
