package com.jamarglex.manijero.lands

import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption

/**
 * The Desktop land store: one human-readable file holding the whole aggregate, plus its bounded
 * same-device automatic copies and the durable purge marker in the same directory.
 *
 * A write goes to a temporary file in the same directory first and then replaces the target in one
 * move, atomically where the file system supports it. A crash, a full disk, or an interrupted write
 * therefore leaves the previous complete value in place instead of a truncated store or copy.
 *
 * The copies are sibling files named `<store>.snapshot-1` (newest) to `<store>.snapshot-3`, and the
 * purge marker is `<store>.purge`. They never leave this directory: no network call and no operating
 * system cloud-backup destination is involved.
 */
class FileLandStorage(private val path: Path) : LandStorage, LandSnapshotStorage {
    override fun read(): String? = if (Files.exists(path)) Files.readString(path) else null

    override fun write(value: String) = writeAtomically(path, value)

    override fun readSnapshots(): List<String> = (1..MAX_AUTOMATIC_LAND_SNAPSHOTS).mapNotNull { slot ->
        val snapshot = snapshotPath(slot)
        if (Files.exists(snapshot)) runCatching { Files.readString(snapshot) }.getOrNull() else null
    }

    override fun writeSnapshot(value: String) {
        for (slot in MAX_AUTOMATIC_LAND_SNAPSHOTS downTo 2) {
            val previous = snapshotPath(slot - 1)
            if (Files.exists(previous)) {
                moveReplacing(previous, snapshotPath(slot))
            } else {
                Files.deleteIfExists(snapshotPath(slot))
            }
        }
        writeAtomically(snapshotPath(1), value)
    }

    override fun replaceSnapshots(values: List<String>) {
        val retained = values.take(MAX_AUTOMATIC_LAND_SNAPSHOTS)
        retained.forEachIndexed { index, value -> writeAtomically(snapshotPath(index + 1), value) }
        for (slot in retained.size + 1..MAX_AUTOMATIC_LAND_SNAPSHOTS) {
            Files.deleteIfExists(snapshotPath(slot))
        }
    }

    override fun readPurgeMarker(): String? {
        val marker = purgeMarkerPath()
        return if (Files.exists(marker)) Files.readString(marker) else null
    }

    override fun writePurgeMarker(value: String?) {
        val marker = purgeMarkerPath()
        if (value == null) {
            Files.deleteIfExists(marker)
        } else {
            writeAtomically(marker, value)
        }
    }

    private fun snapshotPath(slot: Int): Path =
        path.resolveSibling("${path.fileName}.snapshot-$slot")

    private fun purgeMarkerPath(): Path = path.resolveSibling("${path.fileName}.purge")

    private fun writeAtomically(target: Path, value: String) {
        val absolute = target.toAbsolutePath()
        val directory = absolute.parent ?: absolute.fileSystem.getPath(".")
        Files.createDirectories(directory)
        val temporary = Files.createTempFile(directory, "lands", ".tmp")
        try {
            Files.writeString(temporary, value)
            moveReplacing(temporary, absolute)
        } finally {
            Files.deleteIfExists(temporary)
        }
    }

    private fun moveReplacing(from: Path, to: Path) {
        try {
            Files.move(
                from,
                to,
                StandardCopyOption.REPLACE_EXISTING,
                StandardCopyOption.ATOMIC_MOVE,
            )
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(from, to, StandardCopyOption.REPLACE_EXISTING)
        }
    }
}
