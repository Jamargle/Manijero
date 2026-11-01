package com.jamarglex.manijero

import androidx.compose.runtime.remember
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import com.jamarglex.manijero.connection.ActiveServiceAddress
import com.jamarglex.manijero.connection.ConnectionTools
import com.jamarglex.manijero.connection.FileServiceAddressStore
import com.jamarglex.manijero.connection.KtorServiceStatusChecker
import com.jamarglex.manijero.connection.desktopTestBuildEnabled
import com.jamarglex.manijero.lands.AwtBackupFileChooser
import com.jamarglex.manijero.lands.DesktopLandBackupFiles
import com.jamarglex.manijero.lands.FileLandStorage
import com.jamarglex.manijero.lands.LandRepository
import java.nio.file.Path
import java.nio.file.Paths
import io.ktor.client.engine.cio.CIO
import io.ktor.client.HttpClient
import com.jamarglex.manijero.chat.KtorAnswerService
import com.jamarglex.manijero.chat.answerHttpClient
import com.jamarglex.manijero.platform.desktopAskBaseUrl
import com.jamarglex.manijero.platform.desktopPilotToken

/** One stable local file for the lands this person manages on this computer. */
private const val LAND_STORE_DIRECTORY = ".manijero"
private const val LAND_STORE_FILE = "lands-v1.txt"

/** Test builds only: the remembered answer-service address, next to the land store. */
private const val CONNECTION_STORE_FILE = "connection-v1.txt"

fun main() = application {
    val answerClient = remember { answerHttpClient(CIO.create()) }
    val defaultAskBaseUrl = remember { desktopAskBaseUrl() }
    // Only the Gradle development `run` task marks a test build; packaged and release runs keep the
    // fixed answer URL and have no `Conexión` screen.
    val connectionTools = remember { testBuildConnectionTools(defaultAskBaseUrl, answerClient) }
    // The pilot bearer token built in from the git-ignored `pilot-token.local`, or `null`. It is only
    // handed to the answer transport and never shown or logged.
    val pilotToken = remember { desktopPilotToken() }
    val answerService = remember {
        if (connectionTools != null) {
            KtorAnswerService(answerClient, connectionTools.address::current, pilotToken)
        } else {
            KtorAnswerService(answerClient, defaultAskBaseUrl, pilotToken)
        }
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
        App(landRepository, answerService, landBackupFiles, connectionTools)
    }
}

private fun testBuildConnectionTools(defaultUrl: String, client: HttpClient): ConnectionTools? =
    if (desktopTestBuildEnabled()) {
        ConnectionTools(
            address = ActiveServiceAddress(defaultUrl, FileServiceAddressStore(manijeroPath(CONNECTION_STORE_FILE))),
            checker = KtorServiceStatusChecker(client),
        )
    } else {
        null
    }

private fun landStorePath(): Path = manijeroPath(LAND_STORE_FILE)

private fun manijeroPath(file: String): Path = Paths.get(
    System.getProperty("user.home"),
    LAND_STORE_DIRECTORY,
    file,
)
