package com.jamarglex.manijero

import androidx.compose.runtime.remember
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import com.jamarglex.manijero.connection.ActiveServiceAddress
import com.jamarglex.manijero.connection.ConnectionTools
import com.jamarglex.manijero.connection.FileServiceAddressStore
import com.jamarglex.manijero.connection.KtorServiceStatusChecker
import com.jamarglex.manijero.connection.desktopConnectionStorePath
import com.jamarglex.manijero.connection.desktopTestBuildEnabled
import com.jamarglex.manijero.lands.AwtBackupFileChooser
import com.jamarglex.manijero.lands.DesktopLandBackupFiles
import com.jamarglex.manijero.lands.FileLandStorage
import com.jamarglex.manijero.lands.LandRepository
import com.jamarglex.manijero.platform.manijeroAppIcon
import com.jamarglex.manijero.privacy.FileImprovementConsentStore
import com.jamarglex.manijero.privacy.desktopImprovementConsentPath
import com.jamarglex.manijero.welcome.FileWelcomeNoticeStore
import com.jamarglex.manijero.welcome.desktopWelcomeStorePath
import java.nio.file.Path
import java.nio.file.Paths
import io.ktor.client.engine.cio.CIO
import io.ktor.client.HttpClient
import com.jamarglex.manijero.chat.KtorAnswerService
import com.jamarglex.manijero.chat.answerHttpClient
import com.jamarglex.manijero.platform.DesktopEnvironment
import com.jamarglex.manijero.platform.DesktopEnvironmentException
import com.jamarglex.manijero.platform.desktopEnvironment
import com.jamarglex.manijero.platform.desktopPilotToken

/** One stable local file for the lands this person manages on this computer. */
private const val LAND_STORE_FILE = "lands-v1.txt"

fun main() {
    // The environment is built in (local, or QA with its own address and data folder). A malformed
    // setting stops here with a plain message instead of silently running as local.
    val environment = try {
        desktopEnvironment()
    } catch (error: DesktopEnvironmentException) {
        System.err.println(error.message)
        kotlin.system.exitProcess(1)
    }
    runApp(environment)
}

private fun runApp(environment: DesktopEnvironment) = application {
    val answerClient = remember { answerHttpClient(CIO.create()) }
    val defaultAskBaseUrl = remember { environment.defaultAskBaseUrl() }
    // Only the Gradle development `run` task marks a test build; packaged and release runs keep the
    // fixed answer URL and have no `Conexión` screen.
    val connectionTools = remember { testBuildConnectionTools(defaultAskBaseUrl, answerClient, environment.dataFolder) }
    // The pilot bearer token built in from the git-ignored `pilot-token.local`, or `null`. It is only
    // handed to the answer transport and never shown or logged.
    val pilotToken = remember { desktopPilotToken() }
    val answerService = remember {
        if (connectionTools != null) {
            KtorAnswerService(answerClient, connectionTools.address::current, acceptInspection = true, pilotToken = pilotToken)
        } else {
            KtorAnswerService(answerClient, defaultAskBaseUrl, pilotToken)
        }
    }
    val landRepository = remember {
        LandRepository(FileLandStorage(landStorePath(environment.dataFolder)))
    }
    val welcomeNotice = remember { FileWelcomeNoticeStore(desktopWelcomeStorePath(folder = environment.dataFolder)) }
    val improvementConsent = remember {
        FileImprovementConsentStore(desktopImprovementConsentPath(folder = environment.dataFolder))
    }

    Window(
        onCloseRequest = { answerClient.close(); exitApplication() },
        title = environment.title,
        icon = manijeroAppIcon(),
    ) {
        // The portable backup uses the native file dialog, owned by this window so it opens on top.
        val landBackupFiles = remember(window) { DesktopLandBackupFiles(AwtBackupFileChooser(window)) }
        App(landRepository, answerService, landBackupFiles, connectionTools, welcomeNotice, improvementConsent)
    }
}

private fun testBuildConnectionTools(defaultUrl: String, client: HttpClient, folder: String): ConnectionTools? =
    if (desktopTestBuildEnabled()) {
        ConnectionTools(
            address = ActiveServiceAddress(defaultUrl, FileServiceAddressStore(desktopConnectionStorePath(folder = folder))),
            checker = KtorServiceStatusChecker(client),
        )
    } else {
        null
    }

private fun landStorePath(folder: String): Path = Paths.get(
    System.getProperty("user.home"),
    folder,
    LAND_STORE_FILE,
)
