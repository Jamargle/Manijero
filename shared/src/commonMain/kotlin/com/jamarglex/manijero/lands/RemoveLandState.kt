package com.jamarglex.manijero.lands

/** Why the deletion did not happen, so copy and tests can tell the two cases apart. */
enum class RemoveLandFailure { WRITE_FAILED, LAND_MISSING }

/**
 * Pure confirmation state for the "Eliminar terreno" flow.
 *
 * It identifies exactly one loaded [Land] by [landId], which is the only record this state may ever
 * delete, and repeats the known details the row shows so two same-named lands stay distinguishable.
 * The name is the stored, already-trimmed name copied verbatim; an `UNKNOWN` variety or attribute
 * stays `UNKNOWN`, an absent measure stays absent, and the custom variety text is copied only
 * when it exists. [failure] records why a confirmed removal did not happen and is kept separate from
 * the identity fields, so the land still identifies itself for a retry. Ids, timestamps, notes,
 * persistence rules, and resource lookups stay out of this layer. No Compose or platform types belong
 * here.
 */
data class RemoveLandState(
    val landId: String,
    val name: String,
    val zone: String,
    val municipality: String?,
    val waterRegime: WaterRegime,
    val productionMethod: ProductionMethod,
    val variety: LandVariety,
    val varietyOther: String?,
    val areaHectares: Double?,
    val treeCount: Int?,
    val failure: RemoveLandFailure? = null,
)

/**
 * The confirmation target for [this] loaded record: the stored name and every detail the shared
 * `LandDetails` renders are copied verbatim. Nothing is renamed, defaulted, or guessed, and no notes,
 * timestamp, or unrelated value is carried into the confirmation.
 */
fun Land.toRemoveLandState(): RemoveLandState = RemoveLandState(
    landId = id,
    name = name,
    zone = zone,
    municipality = municipality,
    waterRegime = waterRegime,
    productionMethod = productionMethod,
    variety = variety,
    varietyOther = varietyOther,
    areaHectares = areaHectares,
    treeCount = treeCount,
)

sealed interface RemoveLandAction {
    /** The person asked to remove: clears a previous failure so a retry starts clean. */
    data object RemoveClicked : RemoveLandAction

    /** The deletion did not happen; the identity fields are kept so the person can try again. */
    data class RemoveFailed(val failure: RemoveLandFailure) : RemoveLandAction
}

fun RemoveLandState.reduce(action: RemoveLandAction): RemoveLandState = when (action) {
    RemoveLandAction.RemoveClicked -> copy(failure = null)
    is RemoveLandAction.RemoveFailed -> copy(failure = action.failure)
}
