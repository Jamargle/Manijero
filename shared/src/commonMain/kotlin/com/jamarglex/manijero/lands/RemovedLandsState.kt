package com.jamarglex.manijero.lands

/** Why a restore did not happen, so copy and tests can tell the two cases apart. */
enum class RemovedLandsFailure { WRITE_FAILED, LAND_MISSING }

/** What the last successful lifecycle action was, so the list confirms the right thing or nothing. */
enum class RemovedLandsConfirmation { RESTORED, DELETED }

/**
 * Pure state for the "Terrenos eliminados" list.
 *
 * It holds exactly the removed records a read returned, in removal order, plus whether the last read
 * failed, the last success to confirm, and why a restore did not happen. [loadFailed] stays separate
 * from [lands] so a failed read is never presented as an empty removed list, and [failure] stays
 * separate from the records so a refused restore still shows the list it belongs to. Ids, timestamps,
 * persistence rules, and resource lookups stay out of this layer. No Compose or platform types belong
 * here.
 */
data class RemovedLandsState(
    val lands: List<RemovedLand> = emptyList(),
    val loadFailed: Boolean = false,
    val confirmation: RemovedLandsConfirmation? = null,
    val failure: RemovedLandsFailure? = null,
) {
    /** True only for a successful read that found no removed land; a failed read is never "empty". */
    val isEmpty: Boolean
        get() = lands.isEmpty() && !loadFailed
}

sealed interface RemovedLandsAction {
    /** A successful read: keeps the supplied records verbatim and clears the previous result. */
    data class LandsLoaded(val lands: List<RemovedLand>) : RemovedLandsAction

    /** A failed read: discards any previously loaded rows and marks the removed list unreadable. */
    data object LoadFailed : RemovedLandsAction

    /** The person asked to retry: clears rows, failure and confirmation before the caller reads. */
    data object ReloadClicked : RemovedLandsAction

    /** The person asked to restore one record: clears a previous result so a retry starts clean. */
    data object RestoreClicked : RemovedLandsAction

    /** The restore did not happen; the records stay on screen so the person can try again. */
    data class RestoreFailed(val failure: RemovedLandsFailure) : RemovedLandsAction

    /** The record returned to the active list. */
    data object Restored : RemovedLandsAction

    /** A removed record was deleted permanently from the store. */
    data object Deleted : RemovedLandsAction
}

/**
 * Reduces one removed-list action.
 *
 * The three read actions build a **new** [RemovedLandsState] instead of a `copy`, so a re-read clears
 * the previous confirmation and failure. Do not turn them into a `copy`, which would leave a stale
 * "se ha recuperado" notice next to a freshly read list.
 */
fun RemovedLandsState.reduce(action: RemovedLandsAction): RemovedLandsState = when (action) {
    is RemovedLandsAction.LandsLoaded -> RemovedLandsState(lands = action.lands)
    RemovedLandsAction.LoadFailed -> RemovedLandsState(loadFailed = true)
    RemovedLandsAction.ReloadClicked -> RemovedLandsState()
    RemovedLandsAction.RestoreClicked -> copy(confirmation = null, failure = null)
    is RemovedLandsAction.RestoreFailed -> copy(confirmation = null, failure = action.failure)
    RemovedLandsAction.Restored -> copy(
        confirmation = RemovedLandsConfirmation.RESTORED,
        failure = null,
    )

    RemovedLandsAction.Deleted -> copy(
        confirmation = RemovedLandsConfirmation.DELETED,
        failure = null,
    )
}
