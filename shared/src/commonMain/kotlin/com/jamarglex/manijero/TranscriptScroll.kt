package com.jamarglex.manijero

/**
 * What the transcript should move to. It changes only when a new element is appended, so the chat
 * home scrolls once per appended element and never on a plain recomposition.
 *
 * The four fields are exactly the append points of the surface:
 * - [entryCount] — a `Tú` or `Asistente` transcript entry was appended (`ChatHomeState.messages`).
 * - [phase] — the working indication appeared or disappeared (`SubmissionPhase`).
 * - [hasFailure] — a failure notice appeared or cleared (`ChatHomeState.failure`).
 * - [awaitingLandClarification] — the land chooser appeared
 *   (`ChatHomeState.awaitingLandClarification`).
 *
 * A keystroke, an example selection, and any equal-state re-reduction leave every field untouched.
 */
data class TranscriptScrollKey(
    val entryCount: Int,
    val phase: SubmissionPhase,
    val hasFailure: Boolean,
    val awaitingLandClarification: Boolean,
)

/**
 * The pure, testable decision of *when* the newest transcript content has to be brought into view.
 * It is Compose-free so the renderer stays the only place that knows *how* to scroll.
 */
fun transcriptScrollKey(state: ChatHomeState): TranscriptScrollKey = TranscriptScrollKey(
    entryCount = state.messages.size,
    phase = state.phase,
    hasFailure = state.failure != null,
    awaitingLandClarification = state.awaitingLandClarification,
)
