package com.jamarglex.manijero.privacy

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths

/**
 * The Desktop store for the `Ayúdanos a mejorar` choice: the single line `on` or `off` in [path].
 * Anything other than exactly `on` (a missing, empty or unexpected file) reads as off.
 */
class FileImprovementConsentStore(private val path: Path) : ImprovementConsentStore {
    override fun isEnabled(): Boolean =
        Files.exists(path) && Files.readString(path).lineSequence().firstOrNull() == ON

    override fun setEnabled(enabled: Boolean) {
        val absolute = path.toAbsolutePath()
        Files.createDirectories(absolute.parent ?: absolute.fileSystem.getPath("."))
        Files.writeString(absolute, (if (enabled) ON else OFF) + "\n")
    }

    private companion object {
        const val ON = "on"
        const val OFF = "off"
    }
}

/** The Desktop file for the choice, `~/.manijero/improvement-consent-v1.txt`. */
fun desktopImprovementConsentPath(
    home: String = System.getProperty("user.home"),
    folder: String = ".manijero",
): Path = Paths.get(home, folder, "improvement-consent-v1.txt")
