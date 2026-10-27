package com.jamarglex.manijero.lands

import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption

/**
 * The Desktop land store: one human-readable file holding the whole aggregate.
 *
 * A write goes to a temporary file in the same directory first and then replaces the store in one
 * move, atomically where the file system supports it. A crash, a full disk, or an interrupted write
 * therefore leaves the previous complete snapshot in place instead of a truncated store.
 */
class FileLandStorage(private val path: Path) : LandStorage {
    override fun read(): String? = if (Files.exists(path)) Files.readString(path) else null

    override fun write(value: String) {
        val target = path.toAbsolutePath()
        val directory = target.parent ?: target.fileSystem.getPath(".")
        Files.createDirectories(directory)
        val temporary = Files.createTempFile(directory, "lands", ".tmp")
        try {
            Files.writeString(temporary, value)
            try {
                Files.move(
                    temporary,
                    target,
                    StandardCopyOption.REPLACE_EXISTING,
                    StandardCopyOption.ATOMIC_MOVE,
                )
            } catch (_: AtomicMoveNotSupportedException) {
                Files.move(temporary, target, StandardCopyOption.REPLACE_EXISTING)
            }
        } finally {
            Files.deleteIfExists(temporary)
        }
    }
}
