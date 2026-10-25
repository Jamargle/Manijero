package com.jamarglex.manijero.lands

/**
 * Pure state for the "Mis terrenos" list.
 *
 * It holds exactly the lands a read returned, in repository order, plus whether the last read
 * failed, plus the search text the person is typing. [loadFailed] is kept separate from [lands] so
 * a failed read is never presented as an empty list and stale rows never survive a failed reload.
 * [query] is display state only: it is never stored, sent, or logged, and every read starts from a
 * blank query. Ids, timestamps, persistence rules, and resource lookups stay out of this layer. No
 * Compose or platform types belong here.
 */
data class LandListState(
    val lands: List<Land> = emptyList(),
    val loadFailed: Boolean = false,
    val query: String = "",
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

    /**
     * The person changed the search text. It never reorders, reloads, or writes anything; only the
     * shown result set and its summary change.
     */
    data class QueryChanged(val query: String) : LandListAction
}

/**
 * Reduces one list action.
 *
 * The three read actions build a **new** [LandListState] instead of a `copy`, so the appended
 * [LandListState.query] defaults to blank on every read: entering the tab, retrying, and returning
 * from a save, edit or removal all show the full list again. Do not turn them into a `copy`, which
 * would silently keep a stale query.
 */
fun LandListState.reduce(action: LandListAction): LandListState = when (action) {
    is LandListAction.LandsLoaded -> LandListState(lands = action.lands)
    LandListAction.LoadFailed -> LandListState(loadFailed = true)
    LandListAction.ReloadClicked -> LandListState()
    is LandListAction.QueryChanged -> copy(query = action.query)
}
