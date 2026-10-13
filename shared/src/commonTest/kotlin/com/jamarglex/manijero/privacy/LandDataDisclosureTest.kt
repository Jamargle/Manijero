package com.jamarglex.manijero.privacy

import com.jamarglex.manijero.chat.AskRequest
import com.jamarglex.manijero.chat.MinimalLandContext
import com.jamarglex.manijero.chat.answerJson
import com.jamarglex.manijero.chat.askRequestFor
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.lands.ProductionMethod
import com.jamarglex.manijero.lands.WaterRegime
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse

/**
 * The pinned sendable-attribute list and its correspondence with the real encoded request payload:
 * the notice lists exactly the dimensions the request builder can send, so a fourth sendable
 * attribute would fail this test until the notice is updated.
 */
class LandDataDisclosureTest {

    @Test
    fun `the sendable attribute list is the pinned order with no duplicates`() {
        assertEquals(
            listOf(
                SharedLandAttribute.MUNICIPALITY,
                SharedLandAttribute.WATER_REGIME,
                SharedLandAttribute.PRODUCTION_METHOD,
            ),
            SHARED_LAND_ATTRIBUTES,
        )
        assertEquals(
            SharedLandAttribute.entries.toList(),
            SHARED_LAND_ATTRIBUTES,
            "the notice must list every sendable attribute exactly once",
        )
        assertEquals(
            SHARED_LAND_ATTRIBUTES.size,
            SHARED_LAND_ATTRIBUTES.distinct().size,
            "no sendable attribute may be listed twice",
        )
    }

    @Test
    fun `the sendable attribute count matches the encoded payload`() {
        // A fully-populated land and a question that needs every dimension, so the encoded optional
        // keys are exactly the sendable dimensions.
        val land = Land(
            id = "land-1",
            name = "Los Olivos",
            municipality = "Martos",
            waterRegime = WaterRegime.IRRIGATED,
            productionMethod = ProductionMethod.ORGANIC,
            areaHectares = 12.5,
            notes = "Nota privada con teléfono 600 000 000",
            createdAtEpochMillis = 1_700_000_000_000L,
            updatedAtEpochMillis = 1_700_000_111_111L,
        )
        val question = "¿Puedo regar en ecológico en mi municipio?"

        val encoded = answerJson.encodeToString(
            AskRequest.serializer(),
            askRequestFor(question, listOf(land)),
        )

        val encodedLand = Json.parseToJsonElement(encoded)
            .jsonObject
            .getValue("land_context")
            .jsonObject
            .getValue("lands")
            .jsonArray
            .single()
            .jsonObject

        val optionalKeys = encodedLand.keys - "id"
        assertEquals(
            SHARED_LAND_ATTRIBUTES.size,
            optionalKeys.size,
            "the notice lists a different number of attributes than the payload can send",
        )
        assertEquals(
            setOf("municipality", "water_regime", "production_method"),
            optionalKeys,
        )

        listOf("name", "notes", "areaHectares", "createdAt", "updatedAt", "Los Olivos", "Nota privada")
            .forEach { forbidden ->
                assertFalse(
                    encoded.contains(forbidden),
                    "encoded payload must not contain $forbidden",
                )
            }
    }

    @Test
    fun `the notice lists every sendable DTO property`() {
        // `id` is always present; every other declared MinimalLandContext property is a sendable
        // optional dimension. Tying the notice count to the DTO shape fails if a fourth sendable
        // property is ever added.
        val descriptor = MinimalLandContext.serializer().descriptor
        assertEquals(
            SHARED_LAND_ATTRIBUTES.size,
            descriptor.elementsCount - 1,
            "a sendable dimension was added to MinimalLandContext without updating the notice",
        )
    }
}
