package com.jamarglex.manijero.chat

/**
 * Invisible test tags on the assistant surface, read only by test drivers (the local smoke test in
 * `local_end_to_end_smoke`) so they never depend on Spanish copy.
 *
 * A tag is applied with `Modifier.testTag` and nothing else: it never changes semantics, copy, or
 * layout, and no product logic reads it. `LocalSmokeGuardTest` keeps it that way.
 */
object ChatTestTags {
    const val QUESTION_FIELD = "chat.questionField"
    const val ASK_BUTTON = "chat.askButton"
    const val ANSWERED = "chat.answered"
    const val ABSTAINED = "chat.abstained"
    const val SOURCE_CARD = "chat.sourceCard"
    const val LAND_CLARIFICATION = "chat.landClarification"
    const val FAILURE_UNREACHABLE = "chat.failureUnreachable"
    const val FAILURE_SERVICE = "chat.failureService"
    const val RETRY = "chat.retry"
}
