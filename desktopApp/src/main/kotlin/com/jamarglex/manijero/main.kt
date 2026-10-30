package com.jamarglex.manijero

import androidx.compose.runtime.remember
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import com.jamarglex.manijero.lands.AwtBackupFileChooser
import com.jamarglex.manijero.lands.DesktopLandBackupFiles
import com.jamarglex.manijero.lands.FileLandStorage
import com.jamarglex.manijero.lands.LandRepository
import java.nio.file.Path
import java.nio.file.Paths
import io.ktor.client.engine.cio.CIO
import com.jamarglex.manijero.chat.KtorAnswerService
import com.jamarglex.manijero.chat.answerHttpClient
import com.jamarglex.manijero.platform.desktopAskBaseUrl

/** One stable local file for the lands this person manages on this computer. */
private const val LAND_STORE_DIRECTORY = ".manijero"
private const val LAND_STORE_FILE = "lands-v1.txt"

fun main() = application {
    val answerClient = remember { answerHttpClient(CIO.create()) }
    val answerService = remember {
        KtorAnswerService(answerClient, desktopAskBaseUrl())
    }
    val landRepository = remember {
        LandRepository(FileLandStorage(landStorePath()))
    }

    Window(
        onCloseRequest = { answerClient.close(); exitApplication() },
        title = "Manijero",
    ) {
        // The portable backup uses the native file dialog, owned by this window so it opens on top.
        val landBackupFiles = remember(window) { DesktopLandBackupFiles(AwtBackupFileChooser(window)) }
        App(landRepository, answerService, landBackupFiles)
    }
}

private fun landStorePath(): Path = Paths.get(
    System.getProperty("user.home"),
    LAND_STORE_DIRECTORY,
    LAND_STORE_FILE,
)
