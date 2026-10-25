package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.ChatHomeState
import com.jamarglex.manijero.ChatMessage
import com.jamarglex.manijero.Speaker
import com.jamarglex.manijero.chat.AnswerSource
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.lands.LandListState
import com.jamarglex.manijero.lands.LandVariety
import com.jamarglex.manijero.lands.ProductionMethod
import com.jamarglex.manijero.lands.WaterRegime

/**
 * Fixed data for the shared-UI screenshot goldens.
 *
 * Everything here is test-only and code-owned: no clock, no network, no local land store, and no
 * backend fixture is read. The answered reply and its source are copied verbatim from
 * `contracts/examples/response-answered.json` (the accepted sample also used by the screen
 * previews), so the golden depicts the reviewed copy rather than invented legal text. The only
 * addition is the `[1]` citation marker needed to exercise the source-card path.
 */
internal object ScreenshotFixtures {

    private val solicitudUnicaSource = AnswerSource(
        title = "Solicitud única de la PAC",
        issuing_body = "Ministerio de Agricultura, Pesca y Alimentación",
        url = "https://www.mapa.gob.es/",
        location = "Información de la solicitud única",
        published_or_updated_on = "2026-01-15",
        verified_on = "2026-10-01",
        excerpt = "La solicitud única es el procedimiento anual para solicitar determinadas ayudas de la PAC.",
    )

    /** Chat home before any question: suggestions, composer, lands affordance, privacy summary. */
    val idleChat = ChatHomeState()

    /**
     * A supported answer with one cited source, the scope caption, and the source card. This is the
     * densest chat surface; at the fixed 900x1200 viewport the frame ends inside the privacy
     * notice, so the footer links below it are outside this particular golden by design.
     */
    val answeredChat = ChatHomeState(
        messages = listOf(
            ChatMessage(
                speaker = Speaker.USER,
                text = "¿Cuándo puedo presentar la solicitud única?",
            ),
            ChatMessage(
                speaker = Speaker.ASSISTANT,
                text = "La solicitud única reúne determinadas ayudas de la PAC en una declaración anual. [1] " +
                    "Revisa la convocatoria y confirma los requisitos con la oficina agraria antes de presentarla.",
                answerStatus = AnswerStatus.answered,
                sources = listOf(solicitudUnicaSource),
                landScope = LandContextMode.all_active,
            ),
        ),
        lastResponseStatus = AnswerStatus.answered,
    )

    /**
     * An abstained answer: the assistant could not confirm the claim with the reviewed sources.
     * The message is copied verbatim from `contracts/examples/response-abstained.json`, so the
     * captured notice text is the accepted wording and not invented copy.
     */
    val abstainedResponse = ChatHomeState(
        messages = listOf(
            ChatMessage(
                speaker = Speaker.USER,
                text = "¿Cuándo termina el plazo para pedir la ayuda?",
            ),
            ChatMessage(
                speaker = Speaker.ASSISTANT,
                text = "No puedo confirmar ese plazo con la información oficial revisada. " +
                    "Consulta la convocatoria vigente o tu Oficina Comarcal Agraria antes de actuar.",
                answerStatus = AnswerStatus.abstained,
                landScope = LandContextMode.all_active,
            ),
        ),
        lastResponseStatus = AnswerStatus.abstained,
    )

    /**
     * A pending clarification over the two saved lands. The opaque ids match [twoLands], so the
     * chooser can render real stored rows; the screen still filters them, and a failed read would
     * show the accepted fallback instead.
     */
    val clarificationChat = ChatHomeState(
        lastResponseStatus = AnswerStatus.needs_land_clarification,
        landIdsToChoose = listOf("land-1", "land-2"),
    )

    /** Two distinguishable saved lands with known and unknown attributes. */
    val twoLands = LandListState(
        lands = listOf(
            Land(
                id = "land-1",
                name = "Los Olivos",
                zone = "Camino de la Fuente",
                municipality = "Martos",
                variety = LandVariety.PICUAL,
                areaHectares = 1.5,
                treeCount = 85,
                waterRegime = WaterRegime.DRYLAND,
                productionMethod = ProductionMethod.ORGANIC,
                createdAtEpochMillis = 0,
                updatedAtEpochMillis = 0,
            ),
            Land(
                id = "land-2",
                name = "La Loma",
                zone = "Linde del arroyo",
                municipality = "Úbeda",
                variety = LandVariety.OTHER,
                varietyOther = "Royal de Cazorla",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.UNKNOWN,
                createdAtEpochMillis = 0,
                updatedAtEpochMillis = 0,
            ),
        ),
    )

    /** A successful read that found no land: the empty state, never a failure. */
    val noLands = LandListState()

    /**
     * The same two saved lands with a query that matches neither, so the no-results panel renders
     * with no summary cards above it.
     */
    val searchNoResults = twoLands.copy(query = "zzz")

    /**
     * The same two saved lands with a query that matches only `La Loma` (municipality `Úbeda`), so
     * every card describes one match of two saved lands and states that ratio in its caption.
     */
    val searchFiltered = twoLands.copy(query = "ubeda")
}
