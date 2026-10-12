package com.jamarglex.manijero

import androidx.compose.runtime.remember
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import com.jamarglex.manijero.lands.FileLandStorage
import com.jamarglex.manijero.lands.LandRepository
import java.nio.file.Path
import java.nio.file.Paths

/** One stable local file for the lands this person manages on this computer. */
private const val LAND_STORE_DIRECTORY = ".manijero"
private const val LAND_STORE_FILE = "lands-v1.txt"

fun main() = application {
    val landRepository = remember {
        LandRepository(FileLandStorage(landStorePath()))
    }

    Window(
        onCloseRequest = ::exitApplication,
        title = "Manijero",
    ) {
        App(landRepository)
    }
}

private fun landStorePath(): Path = Paths.get(
    System.getProperty("user.home"),
    LAND_STORE_DIRECTORY,
    LAND_STORE_FILE,
)
