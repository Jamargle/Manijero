package com.jamarglex.manijero.chat

import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.lands.ProductionMethod as LocalProductionMethod
import com.jamarglex.manijero.lands.WaterRegime as LocalWaterRegime

/**
 * Which optional land attributes one question actually needs.
 *
 * A `false` dimension means "not needed for this question", so its property stays `null` and
 * `answerJson` (`explicitNulls = false`) omits it from the wire payload. It never means "the value
 * is unknown": a needed dimension whose stored value is unknown is sent as `unknown`.
 */
data class LandContextNeeds(
    val waterRegime: Boolean,
    val productionMethod: Boolean,
    val municipality: Boolean,
)

/**
 * The pinned, reviewable vocabulary for each optional attribute. A dimension is needed only when the
 * folded question contains one of its terms as a **whole token**, so `agua` never matches
 * `aguacate`. Every term is at least four characters. Widening the table is a spec and test change,
 * not a silent one.
 */
private val WATER_REGIME_TERMS = setOf(
    "agua", "aguas", "riego", "riegos", "riega", "riegan", "regar", "regado", "regando", "regadio",
    "secano", "secanos", "goteo", "aspersion", "aspersiones", "drenaje", "lluvia", "lluvias",
    "sequia", "sequias", "humedad", "pozo", "embalse", "balsa", "canal", "acequia",
)

private val PRODUCTION_METHOD_TERMS = setOf(
    "ecologico", "ecologica", "ecologicos", "ecologicas", "convencional", "convencionales",
    "integrada", "integrado", "produccion", "producciones", "organico", "organica", "organicos",
    "organicas", "fertilizante", "fertilizantes", "fertilizacion", "abono", "abonos",
    "fitosanitario", "fitosanitarios", "plaga", "plagas", "herbicida", "herbicidas", "pesticida",
    "pesticidas",
)

private val MUNICIPALITY_TERMS = setOf(
    "municipio", "municipios", "termino", "terminos", "provincia", "provincias", "comarca",
    "comarcas", "localidad", "localidades", "pueblo", "ayuntamiento", "andalucia",
)

/**
 * The attribute dimensions [question] needs, decided by whole-token vocabulary matching on folded
 * text. Nothing is inferred from a land record here, so the same question always yields the same
 * decision.
 */
fun landContextNeeds(question: String): LandContextNeeds {
    val tokens = foldedTokens(question)
    return LandContextNeeds(
        waterRegime = tokens.any(WATER_REGIME_TERMS::contains),
        productionMethod = tokens.any(PRODUCTION_METHOD_TERMS::contains),
        municipality = tokens.any(MUNICIPALITY_TERMS::contains),
    )
}

/**
 * One land reduced to the contract's `MinimalLandContext`: the opaque local id plus only the
 * attributes [needs] asked for. A needed unknown value is sent as `unknown`; an unset municipality is
 * always omitted (the contract has no unknown municipality, and a blank or invented one must never be
 * sent). No name, note, area, or timestamp can appear.
 */
fun minimalLandContext(land: Land, needs: LandContextNeeds): MinimalLandContext = MinimalLandContext(
    id = land.id,
    municipality = land.municipality?.takeIf { it.isNotBlank() }?.takeIf { needs.municipality },
    water_regime = if (needs.waterRegime) land.waterRegime.toChatWaterRegime() else null,
    production_method = if (needs.productionMethod) {
        land.productionMethod.toChatProductionMethod()
    } else {
        null
    },
)

/**
 * The `land_context` for one question. Every stored land is sent (`all_active`) in repository order
 * with its id verbatim whenever at least one land exists, so the service can answer across the
 * person's operation or ask for a choice later; `general` with an empty list is used only when no
 * land is stored. No topic classifier gates the mode: a missed keyword must never silently drop the
 * lands, and a question needing no attribute still sends the ids alone.
 */
fun landContextFor(question: String, lands: List<Land>): LandContext {
    if (lands.isEmpty()) {
        return LandContext(mode = LandContextMode.general, lands = emptyList())
    }
    val needs = landContextNeeds(question)
    return LandContext(
        mode = LandContextMode.all_active,
        lands = lands.map { land -> minimalLandContext(land, needs) },
    )
}

/**
 * The request for one question with the current local lands. It preserves the person's exact wording
 * and never sends more than [landContextFor] allows. With no land stored it delegates to the accepted
 * [generalAskRequest], so the no-land payload stays byte-identical to the accepted one.
 */
fun askRequestFor(question: String, lands: List<Land>): AskRequest {
    if (lands.isEmpty()) return generalAskRequest(question)
    return AskRequest(question = question, land_context = landContextFor(question, lands))
}

/**
 * The request for a land choice: the **exact original wording** with `mode: selected` and only the
 * chosen lands, in the order they were passed, carrying only the attributes the question needs. It is
 * never called with an empty list (the caller degrades to the accepted [generalAskRequest] when a
 * chosen land is no longer stored), it never merges, renames, or reorders a land, and it never invents
 * an id or a value. A `selected` request tells the service the person has already chosen, so it is
 * never asked to clarify again.
 */
fun selectedAskRequest(question: String, selected: List<Land>): AskRequest {
    require(selected.isNotEmpty()) { "selectedAskRequest requires at least one chosen land" }
    val needs = landContextNeeds(question)
    return AskRequest(
        question = question,
        land_context = LandContext(
            mode = LandContextMode.selected,
            lands = selected.map { land -> minimalLandContext(land, needs) },
        ),
    )
}

/**
 * Lowercase plus a fixed, explicit accent table, so `REGADÍO`, `regadio`, and `Regadío` fold to the
 * same token and no locale-dependent case mapping is needed.
 */
private fun fold(character: Char): Char = when (character) {
    'á', 'à', 'ä', 'â' -> 'a'
    'é', 'è', 'ë', 'ê' -> 'e'
    'í', 'ì', 'ï', 'î' -> 'i'
    'ó', 'ò', 'ö', 'ô' -> 'o'
    'ú', 'ù', 'ü', 'û' -> 'u'
    'ñ' -> 'n'
    else -> character
}

/** Maximal runs of letters/digits of the folded text; punctuation and spacing are separators. */
private fun foldedTokens(question: String): List<String> {
    val folded = question.lowercase().map(::fold)
    val tokens = mutableListOf<String>()
    val current = StringBuilder()
    for (character in folded) {
        if (character.isLetterOrDigit()) {
            current.append(character)
        } else if (current.isNotEmpty()) {
            tokens += current.toString()
            current.clear()
        }
    }
    if (current.isNotEmpty()) tokens += current.toString()
    return tokens
}

/** Exhaustive local-to-contract mapping: a new stored value must break compilation, not be mis-sent. */
private fun LocalWaterRegime.toChatWaterRegime(): WaterRegime = when (this) {
    LocalWaterRegime.UNKNOWN -> WaterRegime.unknown
    LocalWaterRegime.DRYLAND -> WaterRegime.dryland
    LocalWaterRegime.IRRIGATED -> WaterRegime.irrigated
    LocalWaterRegime.MIXED -> WaterRegime.mixed
}

/** Exhaustive local-to-contract mapping: a new stored value must break compilation, not be mis-sent. */
private fun LocalProductionMethod.toChatProductionMethod(): ProductionMethod = when (this) {
    LocalProductionMethod.UNKNOWN -> ProductionMethod.unknown
    LocalProductionMethod.CONVENTIONAL -> ProductionMethod.conventional
    LocalProductionMethod.ORGANIC -> ProductionMethod.organic
    LocalProductionMethod.MIXED -> ProductionMethod.mixed
}
