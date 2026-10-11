package com.jamarglex.manijero.lands

import java.nio.file.Files
import java.nio.file.Path

class FileLandStorage(private val path: Path) : LandStorage {
    override fun read(): String? = if (Files.exists(path)) Files.readString(path) else null

    override fun write(value: String) {
        path.parent?.let(Files::createDirectories)
        Files.writeString(path, value)
    }
}
