package com.jamarglex.manijero.lands

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * Composition-scoped owner of the portable backup flow. It applies the pure [reduce] reducer and runs
 * the single in-flight picker or write on [scope], so the screen never touches a file itself.
 *
 * - [export] reads the whole aggregate once, encodes it with [LandBackupFormat], and hands it to the
 *   picker. It writes nothing to the local store.
 * - [chooseFile] reads one file and validates **all** of it before anything else happens. A refused
 *   file only produces a message: the repository is not called at all, so neither the store nor its
 *   automatic copies can change.
 * - [confirmRestore] is the only path that writes, and only for the preview the person is looking at.
 *   [onRestored] lets the caller re-read the lists afterwards.
 *
 * Thrown failures are mapped to payload-free notices; no file content, land value, or exception text
 * is logged or shown.
 */
class LandBackupController(
    private val repository: LandRepository,
    private val files: LandBackupFiles,
    private val scope: CoroutineScope,
    private val onRestored: () -> Unit = {},
) {
    var state: LandBackupState by mutableStateOf(LandBackupState())
        private set

    fun reset() {
        if (!state.working) state = state.reduce(LandBackupAction.Reset)
    }

    fun export() = runExclusive(LandBackupNotice.EXPORT_FAILED) {
        val snapshot = runCatching { repository.snapshot() }.getOrNull()
            ?: return@runExclusive finish(LandBackupNotice.STORE_UNREADABLE)
        val contents = LandBackupFormat.encode(snapshot)
        if (contents.encodeToByteArray().size > MAX_LAND_BACKUP_BYTES) {
            return@runExclusive finish(LandBackupNotice.EXPORT_FAILED)
        }
        val result = files.save(LAND_BACKUP_SUGGESTED_FILE_NAME, contents)
        finish(
            when (result) {
                LandBackupSaveResult.Saved -> LandBackupNotice.EXPORTED
                LandBackupSaveResult.Cancelled -> null
                LandBackupSaveResult.Failed -> LandBackupNotice.EXPORT_FAILED
            },
        )
    }

    fun chooseFile() = runExclusive(LandBackupNotice.OPEN_FAILED) {
        val text = when (val opened = files.open()) {
            is LandBackupOpenResult.Opened -> opened.text
            LandBackupOpenResult.Cancelled -> return@runExclusive finish(null)
            LandBackupOpenResult.TooLarge -> return@runExclusive finish(LandBackupNotice.FILE_TOO_LARGE)
            LandBackupOpenResult.Failed -> return@runExclusive finish(LandBackupNotice.OPEN_FAILED)
        }
        val backup = when (val decoded = LandBackupFormat.decode(text)) {
            is LandBackupDecodeResult.Valid -> decoded.snapshot
            is LandBackupDecodeResult.Invalid -> return@runExclusive finish(decoded.problem.toNotice())
        }
        val current = runCatching { repository.snapshot() }.getOrNull()
            ?: return@runExclusive finish(LandBackupNotice.STORE_UNREADABLE)
        state = state.reduce(
            LandBackupAction.PreviewReady(
                LandBackupPreview(
                    backup = backup,
                    currentActiveCount = current.active.size,
                    currentRemovedCount = current.removed.size,
                ),
            ),
        )
    }

    fun confirmRestore() {
        val preview = state.preview ?: return
        runExclusive(LandBackupNotice.RESTORE_FAILED) {
            when (runCatching { repository.replaceAll(preview.backup) }.getOrNull()) {
                LandReplaceResult.Replaced -> {
                    state = state.reduce(LandBackupAction.Restored)
                    onRestored()
                }

                LandReplaceResult.CurrentUnreadable -> finish(LandBackupNotice.STORE_UNREADABLE)
                LandReplaceResult.StorageFailed, null -> finish(LandBackupNotice.RESTORE_FAILED)
            }
        }
    }

    fun dismissPreview() {
        if (!state.working) state = state.reduce(LandBackupAction.PreviewDismissed)
    }

    private fun finish(notice: LandBackupNotice?) {
        state = state.reduce(LandBackupAction.Finished(notice))
    }

    /** Runs one picker/write at a time; an unexpected failure ends with [failureNotice]. */
    private fun runExclusive(failureNotice: LandBackupNotice, block: suspend () -> Unit) {
        if (state.working) return
        state = state.reduce(LandBackupAction.Started)
        scope.launch {
            try {
                block()
            } catch (cancellation: CancellationException) {
                state = state.reduce(LandBackupAction.Finished(null))
                throw cancellation
            } catch (_: Exception) {
                finish(failureNotice)
            }
        }
    }
}
