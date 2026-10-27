package com.jamarglex.manijero.chat

import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.lands.ProductionMethod as LocalProductionMethod
import com.jamarglex.manijero.lands.WaterRegime as LocalWaterRegime
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * The land-context policy: every active stored land is sent by id, only the attributes the question
 * needs are sent, an unknown value is sent as `unknown`, a value that is not stored is omitted, and the
 * accepted `general` payload is preserved when no land exists. Everything here is a pure function, so
 * the encoded body is asserted byte for byte.
 */
class LandContextBuilderTest {
    private fun land(
        id: String,
        name: String = "Terreno",
        municipality: String? = null,
        waterRegime: LocalWaterRegime = LocalWaterRegime.UNKNOWN,
        productionMethod: LocalProductionMethod = LocalProductionMethod.UNKNOWN,
        areaHectares: Double? = null,
        notes: String? = null,
        createdAtEpochMillis: Long = 1L,
        updatedAtEpochMillis: Long = 1L,
    ) = Land(
        id = id,
        name = name,
        zone = "El Llano",
        municipality = municipality,
        waterRegime = waterRegime,
        productionMethod = productionMethod,
        areaHectares = areaHectares,
        notes = notes,
        createdAtEpochMillis = createdAtEpochMillis,
        updatedAtEpochMillis = updatedAtEpochMillis,
    )

    private fun encoded(request: AskRequest): String =
        answerJson.encodeToString(AskRequest.serializer(), request)

    @Test
    fun `no stored land keeps the accepted general request byte for byte`() {
        val wording = "  ¿Puedo regar hoy?  "

        val request = askRequestFor(wording, emptyList())

        assertEquals(generalAskRequest(wording), request)
        assertEquals(LandContextMode.general, request.land_context.mode)
        assertTrue(request.land_context.lands.isEmpty())
        assertEquals(
            """{"question":"  ¿Puedo regar hoy?  ","land_context":{"mode":"general","lands":[]}}""",
            encoded(request),
        )
    }

    @Test
    fun `a land-relevant question carries every land and only the needed attribute`() {
        val lands = listOf(
            land(
                id = "land-1",
                name = "Los Olivos",
                municipality = "Martos",
                waterRegime = LocalWaterRegime.IRRIGATED,
                productionMethod = LocalProductionMethod.ORGANIC,
            ),
            land(id = "land-2", name = "La Loma"),
        )

        val request = askRequestFor("¿Puedo regar hoy?", lands)

        assertEquals(LandContextMode.all_active, request.land_context.mode)
        assertEquals(listOf("land-1", "land-2"), request.land_context.lands.map { it.id })
        assertEquals(
            MinimalLandContext(id = "land-1", water_regime = WaterRegime.irrigated),
            request.land_context.lands[0],
        )
        assertEquals(
            MinimalLandContext(id = "land-2", water_regime = WaterRegime.unknown),
            request.land_context.lands[1],
        )
        assertEquals(
            """{"question":"¿Puedo regar hoy?","land_context":{"mode":"all_active","lands":""" +
                """[{"id":"land-1","water_regime":"irrigated"},{"id":"land-2","water_regime":"unknown"}]}}""",
            encoded(request),
        )
        listOf(
            "name", "Los Olivos", "La Loma", "notes", "areaHectares", "municipality",
            "production_method", "createdAt", "updatedAt",
        ).forEach { forbidden ->
            assertFalse(encoded(request).contains(forbidden), "encoded body must not contain $forbidden")
        }
    }

    @Test
    fun `only the attribute the question needs is included`() {
        val lands = listOf(
            land(
                id = "land-1",
                name = "Los Olivos",
                municipality = "Martos",
                waterRegime = LocalWaterRegime.IRRIGATED,
                productionMethod = LocalProductionMethod.ORGANIC,
            ),
        )

        val production = askRequestFor("¿Puedo producir en ecológico?", lands).land_context.lands.single()
        assertEquals(MinimalLandContext(id = "land-1", production_method = ProductionMethod.organic), production)
        assertNull(production.municipality)
        assertNull(production.water_regime)

        val municipality = askRequestFor("¿En qué municipio está mi terreno?", lands)
            .land_context.lands.single()
        assertEquals(MinimalLandContext(id = "land-1", municipality = "Martos"), municipality)
        assertNull(municipality.water_regime)
        assertNull(municipality.production_method)

        // The solicitud única deadline matches no attribute vocabulary: the id alone is sent.
        assertEquals(
            """{"question":"¿Cuál es el plazo de la solicitud única?","land_context":{"mode":"all_active","lands":[{"id":"land-1"}]}}""",
            encoded(askRequestFor("¿Cuál es el plazo de la solicitud única?", lands)),
        )
    }

    @Test
    fun `a question matching no vocabulary still carries the lands with ids alone`() {
        val lands = listOf(land("land-1", name = "Los Olivos"), land("land-2", name = "La Loma"))

        val request = askRequestFor("¿Qué documentos necesito?", lands)

        assertEquals(LandContextMode.all_active, request.land_context.mode)
        assertEquals(
            """{"question":"¿Qué documentos necesito?","land_context":{"mode":"all_active","lands":[{"id":"land-1"},{"id":"land-2"}]}}""",
            encoded(request),
        )
    }

    @Test
    fun `unknown is sent as unknown and an unset municipality is omitted`() {
        val lands = listOf(land("land-1", name = "Los Olivos"))

        val water = askRequestFor("¿Puedo regar hoy?", lands).land_context.lands.single()
        assertEquals(WaterRegime.unknown, water.water_regime)
        assertNull(water.municipality)
        assertEquals(
            """{"question":"¿Puedo regar hoy?","land_context":{"mode":"all_active","lands":[{"id":"land-1","water_regime":"unknown"}]}}""",
            encoded(askRequestFor("¿Puedo regar hoy?", lands)),
        )

        val municipal = askRequestFor("¿En qué municipio está?", lands).land_context.lands.single()
        assertNull(municipal.municipality)
        assertEquals(MinimalLandContext(id = "land-1"), municipal)
    }

    @Test
    fun `a blank municipality is omitted even when the question asks for a place`() {
        val lands = listOf(land("land-1", municipality = "   "))

        val land = askRequestFor("¿Cuál es mi término municipal?", lands).land_context.lands.single()

        assertNull(land.municipality)
        assertFalse(encoded(askRequestFor("¿Cuál es mi término municipal?", lands)).contains("municipality"))
    }

    @Test
    fun `accents, case, and plurals fold to the same pinned vocabulary`() {
        assertTrue(landContextNeeds("¿PUEDO REGAR?").waterRegime)
        assertTrue(landContextNeeds("¿Tengo que declarar el regadío?").waterRegime)
        assertTrue(landContextNeeds("¿Cuánta agua necesitan mis secanos?").waterRegime)
        assertTrue(landContextNeeds("¿Puedo usar abonos orgánicos?").productionMethod)
        assertTrue(landContextNeeds("¿Cuál es mi término municipal?").municipality)
        assertTrue(landContextNeeds("¿Estoy en la provincia de Jaén?").municipality)
    }

    @Test
    fun `a whole token is required so a longer word never matches`() {
        val needs = landContextNeeds("¿Vendo aguacates en el pueblo vecino?")

        // `aguacates` is not `agua`; `pueblo` legitimately asks for a place.
        assertFalse(needs.waterRegime)
        assertFalse(needs.productionMethod)
        assertTrue(needs.municipality)

        val noVocabulary = landContextNeeds("¿Quién puede solicitarla?")
        assertFalse(noVocabulary.waterRegime)
        assertFalse(noVocabulary.productionMethod)
        assertFalse(noVocabulary.municipality)
    }

    @Test
    fun `every stored water and production value maps exhaustively`() {
        val waterCases = mapOf(
            LocalWaterRegime.DRYLAND to WaterRegime.dryland,
            LocalWaterRegime.IRRIGATED to WaterRegime.irrigated,
            LocalWaterRegime.MIXED to WaterRegime.mixed,
            LocalWaterRegime.UNKNOWN to WaterRegime.unknown,
        )
        waterCases.forEach { (stored, expected) ->
            val land = askRequestFor(
                "¿Puedo regar hoy?",
                listOf(land("land-1", waterRegime = stored)),
            ).land_context.lands.single()
            assertEquals(expected, land.water_regime)
        }

        val productionCases = mapOf(
            LocalProductionMethod.CONVENTIONAL to ProductionMethod.conventional,
            LocalProductionMethod.ORGANIC to ProductionMethod.organic,
            LocalProductionMethod.MIXED to ProductionMethod.mixed,
            LocalProductionMethod.UNKNOWN to ProductionMethod.unknown,
        )
        productionCases.forEach { (stored, expected) ->
            val land = askRequestFor(
                "¿Producción convencional o ecológica?",
                listOf(land("land-1", productionMethod = stored)),
            ).land_context.lands.single()
            assertEquals(expected, land.production_method)
        }
    }

    @Test
    fun `duplicates, long Unicode names, and private details never reach the payload`() {
        val lands = listOf(
            land(
                id = "land-1",
                name = "Los Olivos",
                areaHectares = 12.5,
                notes = "Nota privada con teléfono 600 000 000",
                createdAtEpochMillis = 1_700_000_000_000L,
                updatedAtEpochMillis = 1_700_000_111_111L,
            ),
            land(
                id = "land-2",
                name = "Los Olivos",
                areaHectares = 3.0,
                notes = "Otra nota privada",
                createdAtEpochMillis = 1_700_000_000_000L,
                updatedAtEpochMillis = 1_700_000_111_111L,
            ),
            land(id = "land-3", name = "Olivar de la ñ «Nueva» 🌳🌳🌳 con un nombre muy largo"),
        )

        val request = askRequestFor("¿Qué documentos necesito?", lands)

        // Nothing is merged, deduplicated, renamed, or reordered.
        assertEquals(listOf("land-1", "land-2", "land-3"), request.land_context.lands.map { it.id })
        assertEquals(
            """{"question":"¿Qué documentos necesito?","land_context":{"mode":"all_active","lands":""" +
                """[{"id":"land-1"},{"id":"land-2"},{"id":"land-3"}]}}""",
            encoded(request),
        )
        listOf("Los Olivos", "Nota privada", "600 000 000", "ñ", "🌳", "12.5", "1700000000000")
            .forEach { forbidden ->
                assertFalse(
                    encoded(request).contains(forbidden),
                    "encoded body must not contain $forbidden",
                )
            }
    }

    @Test
    fun `repository order and opaque ids are preserved verbatim`() {
        val lands = listOf(land("z-9"), land("a-1"), land("land-ñ-42"))

        val request = askRequestFor("¿Puedo regar hoy?", lands)

        assertEquals(listOf("z-9", "a-1", "land-ñ-42"), request.land_context.lands.map { it.id })
    }

    @Test
    fun `each encoded land carries only the contract keys the question needs`() {
        val lands = listOf(
            land(
                id = "land-1",
                name = "Los Olivos",
                municipality = "Martos",
                waterRegime = LocalWaterRegime.IRRIGATED,
                productionMethod = LocalProductionMethod.ORGANIC,
            ),
            land(id = "land-2"),
        )

        val encodedBody = Json.parseToJsonElement(encoded(askRequestFor("¿Puedo regar hoy?", lands)))
            .jsonObject

        assertEquals(setOf("question", "land_context"), encodedBody.keys)
        val context = encodedBody.getValue("land_context").jsonObject
        assertEquals(setOf("mode", "lands"), context.keys)
        context.getValue("lands").jsonArray.forEach { element ->
            // `additionalProperties: false`: id plus the single needed attribute, no null-valued key.
            assertEquals(setOf("id", "water_regime"), element.jsonObject.keys)
        }
    }

    @Test
    fun `the needs decision is deterministic for the same question`() {
        val question = "¿Puedo regar mis secanos con agua de pozo?"

        assertEquals(landContextNeeds(question), landContextNeeds(question))
        assertTrue(landContextNeeds(question).waterRegime)
    }

    @Test
    fun `a selected request keeps the exact wording and only the chosen lands`() {
        val wording = "  ¿Puedo regar hoy?  "
        val chosen = listOf(
            land(id = "land-1", name = "Los Olivos", waterRegime = LocalWaterRegime.IRRIGATED),
            land(id = "land-2", name = "La Loma", waterRegime = LocalWaterRegime.DRYLAND),
        )

        val request = selectedAskRequest(wording, chosen)

        assertEquals(wording, request.question)
        assertEquals(LandContextMode.selected, request.land_context.mode)
        assertEquals(listOf("land-1", "land-2"), request.land_context.lands.map { it.id })
        assertEquals(
            MinimalLandContext(id = "land-1", water_regime = WaterRegime.irrigated),
            request.land_context.lands[0],
        )
        assertEquals(
            MinimalLandContext(id = "land-2", water_regime = WaterRegime.dryland),
            request.land_context.lands[1],
        )
        assertEquals(
            """{"question":"  ¿Puedo regar hoy?  ","land_context":{"mode":"selected","lands":""" +
                """[{"id":"land-1","water_regime":"irrigated"},{"id":"land-2","water_regime":"dryland"}]}}""",
            encoded(request),
        )
        listOf(
            "name", "Los Olivos", "La Loma", "notes", "areaHectares", "municipality",
            "production_method", "createdAt", "updatedAt",
        ).forEach { forbidden ->
            assertFalse(encoded(request).contains(forbidden), "encoded body must not contain $forbidden")
        }
    }

    @Test
    fun `a selected request carries only the attribute the question needs`() {
        val chosen = listOf(
            land(
                id = "land-1",
                name = "Los Olivos",
                municipality = "Martos",
                waterRegime = LocalWaterRegime.IRRIGATED,
                productionMethod = LocalProductionMethod.ORGANIC,
            ),
            land(id = "land-2", name = "La Loma", productionMethod = LocalProductionMethod.CONVENTIONAL),
        )

        val production = selectedAskRequest("¿Puedo producir en ecológico?", chosen)
        assertEquals(
            listOf(
                MinimalLandContext(id = "land-1", production_method = ProductionMethod.organic),
                MinimalLandContext(id = "land-2", production_method = ProductionMethod.conventional),
            ),
            production.land_context.lands,
        )
        assertEquals(
            """{"question":"¿Puedo producir en ecológico?","land_context":{"mode":"selected","lands":""" +
                """[{"id":"land-1","production_method":"organic"},{"id":"land-2","production_method":"conventional"}]}}""",
            encoded(production),
        )
        // A question matching no vocabulary sends the chosen ids alone, in the order passed.
        assertEquals(
            """{"question":"¿Qué documentos necesito?","land_context":{"mode":"selected","lands":""" +
                """[{"id":"land-1"},{"id":"land-2"}]}}""",
            encoded(selectedAskRequest("¿Qué documentos necesito?", chosen)),
        )
    }

    @Test
    fun `a selected request requires at least one chosen land`() {
        val failure = runCatching { selectedAskRequest("¿Puedo regar hoy?", emptyList()) }

        assertTrue(failure.isFailure)
    }
}
