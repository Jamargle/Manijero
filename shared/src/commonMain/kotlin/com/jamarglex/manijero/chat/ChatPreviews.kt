package com.jamarglex.manijero.chat

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.ChatHomeState
import com.jamarglex.manijero.ChatMessage
import com.jamarglex.manijero.Speaker
import com.jamarglex.manijero.SubmissionPhase
import com.jamarglex.manijero.chat.AnswerSource
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.lands.LandVariety
import com.jamarglex.manijero.lands.ProductionMethod
import com.jamarglex.manijero.lands.WaterRegime
import com.jamarglex.manijero.theme.ManijeroTheme

// Preview-only samples. The answered and abstention texts are pinned code-owned messages copied
// verbatim from the accepted contracts; the sources come from contracts/examples/response-answered.json.
// Nothing here is shipped copy, and no preview reads a clock, a store, or the network.
private const val ANSWERED_SAMPLE =
    "Según los documentos oficiales revisados: presenta la solicitud dentro del plazo indicado en la convocatoria. [1] " +
        "Información orientativa basada en documentos oficiales. No sustituye el asesoramiento profesional."

// Preview-only two-source answer body: the accepted fixture's answer text with a `[1]`/`[2]` marker
// on each sentence, so the two duplicated source cards are numbered. No claim text is invented.
private const val ANSWERED_TWO_SOURCES_SAMPLE =
    "La solicitud única reúne determinadas ayudas de la PAC en una declaración anual. [1] " +
        "Revisa la convocatoria y confirma los requisitos con la oficina agraria antes de presentarla. [2]"

// Preview-only source sample, copied verbatim from contracts/examples/response-answered.json.
private val SOURCE_SAMPLE = listOf(
    AnswerSource(
        title = "Solicitud única de la PAC",
        issuing_body = "Ministerio de Agricultura, Pesca y Alimentación",
        url = "https://www.mapa.gob.es/",
        location = "Información de la solicitud única",
        published_or_updated_on = "2026-01-15",
        verified_on = "2026-10-01",
        excerpt = "La solicitud única es el procedimiento anual para solicitar determinadas ayudas de la PAC.",
    ),
)

// The accepted sample duplicated, preview-only, so the two-card layout is exercised.
private val SOURCE_SAMPLE_TWO = SOURCE_SAMPLE + SOURCE_SAMPLE

private const val ABSTAINED_SAMPLE_NO_EVIDENCE =
    "No he encontrado esta información en los documentos oficiales que tengo. " +
        "Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."

private const val ABSTAINED_SAMPLE_FALSE_PREMISE =
    "No puedo confirmar ese dato con los documentos oficiales revisados. " +
        "Comprueba el nombre o el número exacto con tu oficina comarcal agraria o con tu cooperativa."

@Preview(name = "Chat home with examples")
@Composable
private fun ChatHomePreview() {
    ManijeroTheme { ChatHomeScreen(ChatHomeState(), {}) }
}

@Preview(name = "Chat home with privacy summary and control")
@Composable
private fun ChatHomePrivacyPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(),
            onAction = {},
            onPrivacyClick = {},
        )
    }
}

@Preview(name = "Chat home narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeSuggestionsNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(question = "¿Qué obligaciones tengo por la condicionalidad?"),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home with question")
@Composable
private fun ChatHomeWithQuestionPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(question = "¿Cuándo debo revisar mi olivar?"),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home wide window", widthDp = 1000)
@Composable
private fun ChatHomeWideWindowPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(Speaker.ASSISTANT, ANSWERED_SAMPLE, AnswerStatus.answered, SOURCE_SAMPLE),
                ),
            ),
            onAction = {},
            onPrivacyClick = {},
        )
    }
}

@Preview(name = "Chat home long conversation, large text", fontScale = 1.3f)
@Composable
private fun ChatHomeLongConversationLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                question = "¿Puedo regar hoy?",
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Cuánto cuesta matricular un tractor viejo?"),
                    ChatMessage(Speaker.ASSISTANT, ABSTAINED_SAMPLE_NO_EVIDENCE, AnswerStatus.abstained),
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(Speaker.ASSISTANT, ANSWERED_SAMPLE, AnswerStatus.answered, SOURCE_SAMPLE),
                    ChatMessage(Speaker.USER, "¿Qué obligaciones tengo por la condicionalidad?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_TWO_SOURCES_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE_TWO,
                        LandContextMode.all_active,
                    ),
                ),
            ),
            onAction = {},
            onPrivacyClick = {},
        )
    }
}

@Preview(name = "Chat home with answered response and one source")
@Composable
private fun ChatHomeAnsweredConversationPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(Speaker.ASSISTANT, ANSWERED_SAMPLE, AnswerStatus.answered, SOURCE_SAMPLE),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home with answered response and two sources")
@Composable
private fun ChatHomeAnsweredTwoSourcesPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_TWO_SOURCES_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE_TWO,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home source card narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeSourceCardNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_TWO_SOURCES_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE_TWO,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home land scope, all lands")
@Composable
private fun ChatHomeLandScopeAllActivePreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE,
                        LandContextMode.all_active,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home land scope, selected lands")
@Composable
private fun ChatHomeLandScopeSelectedPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE,
                        LandContextMode.selected,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home land scope, abstention with all lands")
@Composable
private fun ChatHomeLandScopeAbstainedPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Cuánto cuesta matricular un tractor viejo?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ABSTAINED_SAMPLE_NO_EVIDENCE,
                        AnswerStatus.abstained,
                        emptyList(),
                        LandContextMode.all_active,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home land scope narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeLandScopeNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE,
                        LandContextMode.selected,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home with abstained response")
@Composable
private fun ChatHomeAbstainedConversationPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Cuánto cuesta matricular un tractor viejo?"),
                    ChatMessage(Speaker.ASSISTANT, ABSTAINED_SAMPLE_NO_EVIDENCE, AnswerStatus.abstained),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home with both response states")
@Composable
private fun ChatHomeBothResponseStatesPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Cuánto cuesta matricular un tractor viejo?"),
                    ChatMessage(Speaker.ASSISTANT, ABSTAINED_SAMPLE_NO_EVIDENCE, AnswerStatus.abstained),
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(Speaker.ASSISTANT, ANSWERED_SAMPLE, AnswerStatus.answered, SOURCE_SAMPLE),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home abstention narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeAbstentionNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué dice el Real Decreto 123/2099 sobre el plazo?"),
                    ChatMessage(Speaker.ASSISTANT, ABSTAINED_SAMPLE_FALSE_PREMISE, AnswerStatus.abstained),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home while working")
@Composable
private fun ChatHomeWorkingPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(ChatMessage(Speaker.USER, "¿Puedo regar hoy?")),
                phase = SubmissionPhase.SUBMITTING,
                submittedQuestion = "¿Puedo regar hoy?",
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home over character limit")
@Composable
private fun ChatHomeOverLimitPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(question = "a".repeat(2_100)),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home failure, unreachable service")
@Composable
private fun ChatHomeFailureUnreachablePreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                question = "¿Puedo regar hoy?",
                messages = listOf(ChatMessage(Speaker.USER, "¿Puedo regar hoy?")),
                failure = RequestFailure.COULD_NOT_REACH_SERVICE,
                failedQuestion = "¿Puedo regar hoy?",
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home failure narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeFailureNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                question = "¿Qué necesito preparar para la solicitud única?",
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                ),
                failure = RequestFailure.SERVICE_ERROR,
                failedQuestion = "¿Qué necesito preparar para la solicitud única?",
            ),
            onAction = {},
        )
    }
}

// Preview-only sample lands for the chooser: the saved-name title plus known attributes, nothing a
// real store would not hold. The ids are opaque local ids and are never shown.
@Suppress("LongParameterList")
private fun clarificationLand(
    id: String,
    name: String,
    zone: String = "El Llano",
    municipality: String? = null,
    variety: LandVariety = LandVariety.UNKNOWN,
    varietyOther: String? = null,
    areaHectares: Double? = null,
    treeCount: Int? = null,
    waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
) = Land(
    id = id,
    name = name,
    zone = zone,
    municipality = municipality,
    variety = variety,
    varietyOther = varietyOther,
    areaHectares = areaHectares,
    treeCount = treeCount,
    waterRegime = waterRegime,
    productionMethod = productionMethod,
    createdAtEpochMillis = 0,
    updatedAtEpochMillis = 0,
)

@Preview(name = "Chat home clarification chooser while the local read resolves")
@Composable
private fun ChatHomeClarificationLoadingPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                lastResponseStatus = AnswerStatus.needs_land_clarification,
                landIdsToChoose = listOf("land-1", "land-2"),
            ),
            onAction = {},
            // `null` is the unresolved guarded local read: title and explanation only, never the
            // "no puedo mostrar tus terrenos" fallback.
            clarificationLands = null,
        )
    }
}

@Preview(name = "Chat home clarification chooser, two lands")
@Composable
private fun ChatHomeClarificationTwoLandsPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                lastResponseStatus = AnswerStatus.needs_land_clarification,
                landIdsToChoose = listOf("land-1", "land-2"),
            ),
            onAction = {},
            clarificationLands = listOf(
                clarificationLand(
                    id = "land-1",
                    name = "Los Olivos",
                    zone = "Camino de la Fuente",
                    variety = LandVariety.PICUAL,
                    areaHectares = 1.5,
                    treeCount = 85,
                    waterRegime = WaterRegime.IRRIGATED,
                ),
                clarificationLand(
                    id = "land-2",
                    name = "La Loma",
                    zone = "Linde del arroyo",
                    variety = LandVariety.OTHER,
                    varietyOther = "Royal de Cazorla",
                    waterRegime = WaterRegime.DRYLAND,
                ),
            ),
        )
    }
}

@Preview(name = "Chat home clarification chooser, one land")
@Composable
private fun ChatHomeClarificationOneLandPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                lastResponseStatus = AnswerStatus.needs_land_clarification,
                landIdsToChoose = listOf("land-1"),
            ),
            onAction = {},
            clarificationLands = listOf(
                clarificationLand(
                    id = "land-1",
                    name = "Los Olivos",
                    zone = "Camino de la Fuente",
                    municipality = "Martos",
                    variety = LandVariety.ARBEQUINA,
                    areaHectares = 2.5,
                    treeCount = 85,
                    productionMethod = ProductionMethod.ORGANIC,
                ),
            ),
        )
    }
}

@Preview(name = "Chat home clarification chooser narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeClarificationNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                lastResponseStatus = AnswerStatus.needs_land_clarification,
                landIdsToChoose = listOf("land-1", "land-2"),
            ),
            onAction = {},
            clarificationLands = listOf(
                clarificationLand(
                    id = "land-1",
                    name = "Los Olivos",
                    zone = "Camino de la Fuente",
                    variety = LandVariety.PICUAL,
                    areaHectares = 1.5,
                    treeCount = 85,
                    waterRegime = WaterRegime.IRRIGATED,
                ),
                clarificationLand(
                    id = "land-2",
                    name = "La Loma",
                    zone = "Linde del arroyo",
                    variety = LandVariety.OTHER,
                    varietyOther = "Royal de Cazorla",
                    waterRegime = WaterRegime.DRYLAND,
                ),
            ),
        )
    }
}
