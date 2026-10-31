package com.jamarglex.manijero.lands

import java.awt.FileDialog
import java.awt.Frame
import java.io.InputStream
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** The native file dialog seam, so the file handling is testable without a window. */
interface DesktopBackupFileChooser {
    /** The place the person chose to save to, or `null` when they cancelled. */
    fun chooseSaveTarget(suggestedFileName: String): Path?

    /** The file the person chose to open, or `null` when they cancelled. */
    fun chooseOpenSource(): Path?
}

/**
 * The macOS/Desktop native file dialog (`java.awt.FileDialog`, the system panel on macOS). It is
 * modal and runs on the calling (UI) thread, as AWT expects.
 */
class AwtBackupFileChooser(private val owner: Frame? = null) : DesktopBackupFileChooser {
    override fun chooseSaveTarget(suggestedFileName: String): Path? =
        show(FileDialog.SAVE) { file = suggestedFileName }

    override fun chooseOpenSource(): Path? = show(FileDialog.LOAD) {}

    private fun show(mode: Int, configure: FileDialog.() -> Unit): Path? {
        val dialog = FileDialog(owner, null, mode).apply(configure)
        dialog.isVisible = true
        val directory = dialog.directory ?: return null
        val name = dialog.file ?: return null
        return Path.of(directory, name)
    }
}

/**
 * Desktop [LandBackupFiles]: the person picks the location with [chooser]; the file is written whole
 * to a temporary sibling and moved into place, so a failed write never leaves half a backup. Reading
 * stops after [MAX_LAND_BACKUP_BYTES] + 1 bytes. File work runs on [ioDispatcher]; nothing else is
 * kept, copied, or sent anywhere.
 */
class DesktopLandBackupFiles(
    private val chooser: DesktopBackupFileChooser = AwtBackupFileChooser(),
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : LandBackupFiles {
    override suspend fun save(suggestedFileName: String, contents: String): LandBackupSaveResult {
        val chosen = runCatching { chooser.chooseSaveTarget(suggestedFileName) }
            .getOrElse { return LandBackupSaveResult.Failed }
            ?: return LandBackupSaveResult.Cancelled
        val target = withJsonExtension(chosen)
        return withContext(ioDispatcher) {
            runCatching { writeWhole(target, contents) }
                .fold(onSuccess = { LandBackupSaveResult.Saved }, onFailure = { LandBackupSaveResult.Failed })
        }
    }

    override suspend fun open(): LandBackupOpenResult {
        val source = runCatching { chooser.chooseOpenSource() }
            .getOrElse { return LandBackupOpenResult.Failed }
            ?: return LandBackupOpenResult.Cancelled
        return withContext(ioDispatcher) {
            runCatching { Files.newInputStream(source).use(::readBounded) }
                .fold(onSuccess = ::landBackupOpenResultFromBytes, onFailure = { LandBackupOpenResult.Failed })
        }
    }

    private fun withJsonExtension(path: Path): Path {
        val name = path.fileName?.toString() ?: return path
        return if (name.endsWith(".json", ignoreCase = true)) path else path.resolveSibling("$name.json")
    }

    private fun writeWhole(target: Path, contents: String) {
        val absolute = target.toAbsolutePath()
        val directory = absolute.parent ?: absolute.fileSystem.getPath(".")
        val temporary = Files.createTempFile(directory, ".manijero-backup", ".tmp")
        try {
            Files.writeString(temporary, contents, Charsets.UTF_8)
            try {
                Files.move(
                    temporary,
                    absolute,
                    StandardCopyOption.REPLACE_EXISTING,
                    StandardCopyOption.ATOMIC_MOVE,
                )
            } catch (_: AtomicMoveNotSupportedException) {
                Files.move(temporary, absolute, StandardCopyOption.REPLACE_EXISTING)
            }
        } finally {
            Files.deleteIfExists(temporary)
        }
    }
}

/** Reads at most [MAX_LAND_BACKUP_BYTES] + 1 bytes, enough to tell an oversized file apart. */
internal fun readBounded(input: InputStream): ByteArray = input.readNBytes(MAX_LAND_BACKUP_BYTES + 1)
