package com.jamarglex.manijero.welcome

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths

/** The Desktop store for the welcome-dismissed flag: the single line `dismissed` in [path]. */
class FileWelcomeNoticeStore(private val path: Path) : WelcomeNoticeStore {
    override fun isDismissed(): Boolean =
        Files.exists(path) && Files.readString(path).lineSequence().firstOrNull() == DISMISSED

    override fun markDismissed() {
        val absolute = path.toAbsolutePath()
        Files.createDirectories(absolute.parent ?: absolute.fileSystem.getPath("."))
        Files.writeString(absolute, DISMISSED + "\n")
    }

    private companion object {
        const val DISMISSED = "dismissed"
    }
}

/** The Desktop file for the welcome flag, `~/.manijero/welcome-v1.txt`. */
fun desktopWelcomeStorePath(
    home: String = System.getProperty("user.home"),
    folder: String = ".manijero",
): Path = Paths.get(home, folder, "welcome-v1.txt")
