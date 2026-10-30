package com.jamarglex.manijero.lands

/**
 * The platform file picker for portable land backups. Android implements it with the system
 * document picker and Desktop with the native file dialog; shared code never sees a path or a URI.
 *
 * The person chooses the location every time: the app keeps no reference to the file afterwards,
 * never copies it anywhere else, and never deletes it. Implementations MUST NOT use a network, an
 * account, or a cloud destination of their own.
 */
interface LandBackupFiles {
    /** Asks the person where to save [contents] (suggesting [suggestedFileName]) and writes it there. */
    suspend fun save(suggestedFileName: String, contents: String): LandBackupSaveResult

    /** Asks the person for a file and reads it, bounded by [MAX_LAND_BACKUP_BYTES]. */
    suspend fun open(): LandBackupOpenResult
}

enum class LandBackupSaveResult {
    /** The whole file was written where the person chose. */
    Saved,

    /** The person closed the picker without choosing a place; nothing was written. */
    Cancelled,

    /** The chosen place could not be written. */
    Failed,
}

sealed interface LandBackupOpenResult {
    /** The chosen file's complete text. It has not been validated yet. */
    data class Opened(val text: String) : LandBackupOpenResult

    /** The person closed the picker without choosing a file. */
    data object Cancelled : LandBackupOpenResult

    /** The chosen file is larger than [MAX_LAND_BACKUP_BYTES]; it was not read into memory. */
    data object TooLarge : LandBackupOpenResult

    /** The chosen file could not be read, or it is not UTF-8 text. */
    data object Failed : LandBackupOpenResult
}

/**
 * Maps the bytes a picker adapter read to an open result. [bytes] holds at most
 * [MAX_LAND_BACKUP_BYTES] + 1 bytes, so an adapter can stop reading as soon as the limit is passed.
 * Invalid UTF-8 is refused instead of being silently replaced.
 */
fun landBackupOpenResultFromBytes(bytes: ByteArray): LandBackupOpenResult {
    if (bytes.size > MAX_LAND_BACKUP_BYTES) return LandBackupOpenResult.TooLarge
    return runCatching { bytes.decodeToString(throwOnInvalidSequence = true) }
        .fold(
            onSuccess = { LandBackupOpenResult.Opened(it) },
            onFailure = { LandBackupOpenResult.Failed },
        )
}
