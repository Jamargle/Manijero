package com.jamarglex.manijero.lands

/** The one message the backup screen shows after an action, so copy and tests can tell them apart. */
enum class LandBackupNotice {
    EXPORTED,
    EXPORT_FAILED,
    STORE_UNREADABLE,
    OPEN_FAILED,
    FILE_TOO_LARGE,
    NOT_A_BACKUP,
    UNSUPPORTED_VERSION,
    DAMAGED,
    INVALID_CONTENT,
    RESTORED,
    RESTORE_FAILED,
}

/**
 * A fully validated backup waiting for the person's replace-all decision, with the counts it would
 * replace. Nothing has been written while a preview is on screen.
 */
data class LandBackupPreview(
    val backup: LandSnapshot,
    val currentActiveCount: Int,
    val currentRemovedCount: Int,
)

/**
 * Pure state for the `Copia en un archivo` screen. [working] is true while a picker or a write is in
 * flight, so a second tap cannot open a second dialog or restore twice. No Compose or platform type
 * belongs here.
 */
data class LandBackupState(
    val working: Boolean = false,
    val preview: LandBackupPreview? = null,
    val notice: LandBackupNotice? = null,
)

sealed interface LandBackupAction {
    /** An export, a file choice, or a confirmed restore started: clears the previous message. */
    data object Started : LandBackupAction

    /**
     * The action ended with [notice], or with no message at all when the person cancelled. A pending
     * preview stays, so a refused restore can be retried or cancelled.
     */
    data class Finished(val notice: LandBackupNotice?) : LandBackupAction

    /** A valid file was read and is waiting for confirmation. */
    data class PreviewReady(val preview: LandBackupPreview) : LandBackupAction

    /** The backup replaced both lists: the preview closes and the success is confirmed. */
    data object Restored : LandBackupAction

    /** The person declined the replacement; nothing was written. */
    data object PreviewDismissed : LandBackupAction

    /** The screen was opened again: start from a clean state. */
    data object Reset : LandBackupAction
}

fun LandBackupState.reduce(action: LandBackupAction): LandBackupState = when (action) {
    LandBackupAction.Started -> copy(working = true, notice = null)
    is LandBackupAction.Finished -> copy(working = false, notice = action.notice)
    is LandBackupAction.PreviewReady -> LandBackupState(preview = action.preview)
    LandBackupAction.Restored -> LandBackupState(notice = LandBackupNotice.RESTORED)
    LandBackupAction.PreviewDismissed -> LandBackupState()
    LandBackupAction.Reset -> LandBackupState()
}

/** The message a refused file shows. Every one also says that nothing was changed. */
fun LandBackupProblem.toNotice(): LandBackupNotice = when (this) {
    LandBackupProblem.TOO_LARGE -> LandBackupNotice.FILE_TOO_LARGE
    LandBackupProblem.NOT_A_BACKUP -> LandBackupNotice.NOT_A_BACKUP
    LandBackupProblem.UNSUPPORTED_VERSION -> LandBackupNotice.UNSUPPORTED_VERSION
    LandBackupProblem.DAMAGED -> LandBackupNotice.DAMAGED
    LandBackupProblem.INVALID_CONTENT -> LandBackupNotice.INVALID_CONTENT
}
