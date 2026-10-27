package com.jamarglex.manijero.lands

/** Why the permanent deletion did not happen, so copy and tests can tell the two cases apart. */
enum class PermanentlyDeleteFailure { WRITE_FAILED, LAND_MISSING }

/**
 * Pure confirmation state for deleting one removed land for good.
 *
 * It identifies exactly one removed [RemovedLand] by [landId], the only record this state may ever
 * delete, and repeats the known details the removed-list row shows so two same-named lands stay
 * distinguishable. The name is the stored, already-trimmed name copied verbatim; an `UNKNOWN`
 * variety or attribute stays `UNKNOWN`, an absent measure stays absent, and the custom variety text
 * is copied only when it exists. [failure] records why a confirmed deletion did not happen and stays
 * separate from the identity fields, so the land still identifies itself for a retry. Notes,
 * timestamps, persistence rules, and resource lookups stay out of this layer. No Compose or platform
 * types belong here.
 */
data class PermanentlyDeleteLandState(
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
    val failure: PermanentlyDeleteFailure? = null,
)

/**
 * The confirmation target for [this] removed record: the stored name and every detail the shared
 * `LandDetails` renders are copied verbatim. Nothing is renamed, defaulted, or guessed, and no notes,
 * removal timestamp, or unrelated value is carried into the confirmation.
 */
fun RemovedLand.toPermanentlyDeleteLandState(): PermanentlyDeleteLandState =
    PermanentlyDeleteLandState(
        landId = land.id,
        name = land.name,
        zone = land.zone,
        municipality = land.municipality,
        waterRegime = land.waterRegime,
        productionMethod = land.productionMethod,
        variety = land.variety,
        varietyOther = land.varietyOther,
        areaHectares = land.areaHectares,
        treeCount = land.treeCount,
    )

sealed interface PermanentlyDeleteLandAction {
    /** The person confirmed: clears a previous failure so a retry starts clean. */
    data object DeleteClicked : PermanentlyDeleteLandAction

    /** The deletion did not happen; the identity fields are kept so the person can try again. */
    data class DeleteFailed(val failure: PermanentlyDeleteFailure) : PermanentlyDeleteLandAction
}

fun PermanentlyDeleteLandState.reduce(
    action: PermanentlyDeleteLandAction,
): PermanentlyDeleteLandState = when (action) {
    PermanentlyDeleteLandAction.DeleteClicked -> copy(failure = null)
    is PermanentlyDeleteLandAction.DeleteFailed -> copy(failure = action.failure)
}
