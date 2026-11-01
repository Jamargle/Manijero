package com.jamarglex.manijero.connection

import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption

/**
 * The Desktop test-build store for the remembered answer-service address: one UTF-8 line in [path]
 * (by default `~/.manijero/connection-v1.txt`). A write goes to a temporary file in the same
 * directory and then replaces the target in one move, so a failed write never leaves a partial
 * file. Release and packaged builds never construct it.
 */
class FileServiceAddressStore(private val path: Path) : ServiceAddressStore {
    override fun load(): String? =
        if (Files.exists(path)) Files.readString(path).lineSequence().firstOrNull()?.trim() else null

    override fun save(address: String) {
        val absolute = path.toAbsolutePath()
        val directory = absolute.parent ?: absolute.fileSystem.getPath(".")
        Files.createDirectories(directory)
        val temporary = Files.createTempFile(directory, "connection", ".tmp")
        try {
            Files.writeString(temporary, address + "\n")
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

    override fun clear() {
        Files.deleteIfExists(path)
    }
}
