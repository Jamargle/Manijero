package com.jamarglex.manijero.lands

/**
 * Pure state for the "Mis terrenos" list.
 *
 * It holds exactly the lands a read returned, in repository order, plus whether the last read
 * failed. [loadFailed] is kept separate from [lands] so a failed read is never presented as an
 * empty list and stale rows never survive a failed reload. Ids, timestamps, persistence rules, and
 * resource lookups stay out of this layer. No Compose or platform types belong here.
 */
data class LandListState(
    val lands: List<Land> = emptyList(),
    val loadFailed: Boolean = false,
) {
    /** True only for a successful read that found no land; a failed read is never "empty". */
    val isEmpty: Boolean
        get() = lands.isEmpty() && !loadFailed
}

sealed interface LandListAction {
    /** A successful read: keeps the supplied list verbatim and clears any previous failure. */
    data class LandsLoaded(val lands: List<Land>) : LandListAction

    /** A failed read: discards any previously loaded rows and marks the list unreadable. */
    data object LoadFailed : LandListAction

    /** The person asked to retry: clears rows and the failure before the caller reads again. */
    data object ReloadClicked : LandListAction
}

fun LandListState.reduce(action: LandListAction): LandListState = when (action) {
    is LandListAction.LandsLoaded -> LandListState(lands = action.lands)
    LandListAction.LoadFailed -> LandListState(loadFailed = true)
    LandListAction.ReloadClicked -> LandListState()
}
