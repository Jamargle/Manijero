package com.jamarglex.manijero.lands

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.App
import java.nio.file.Files
import kotlin.test.Test

/**
 * The land search lives in the top bar of `Mis terrenos`: a visible magnifier (not inside a menu),
 * a field that filters the list, and closing that clears the filter. Synthetic lands only.
 */
@OptIn(ExperimentalTestApi::class)
class LandSearchTopBarInteractionTest {
    @Test
    fun theMagnifierOpensTheFieldFiltersTheListAndClosingClearsIt() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            val directory = Files.createTempDirectory("manijero-search-flow")
            try {
                val repository = LandRepository(FileLandStorage(directory.resolve("lands.txt")))
                repository.create(LandDraft("Los Olivos", "El Llano"), now = 1)
                repository.create(LandDraft("La Loma", "La Umbría"), now = 2)
                setContent { App(landRepository = repository) }

                onNodeWithText("Los Olivos").assertExists()
                onNodeWithContentDescription("Buscar terreno").assertHeightIsAtLeast(48.dp).performClick()
                onNodeWithText("Buscar por nombre, municipio o tipo…").performTextInput("loma")

                onNodeWithText("La Loma").assertExists()
                onNodeWithText("Los Olivos").assertDoesNotExist()

                onNodeWithContentDescription("Cerrar la búsqueda").performClick()
                onNodeWithText("Los Olivos").assertExists()
                onNodeWithText("La Loma").assertExists()
                onNodeWithContentDescription("Buscar terreno").assertExists()
            } finally {
                directory.toFile().deleteRecursively()
            }
        }

    @Test
    fun withNoLandsThereIsNothingToSearch() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            val directory = Files.createTempDirectory("manijero-search-empty")
            try {
                val repository = LandRepository(FileLandStorage(directory.resolve("lands.txt")))
                setContent { App(landRepository = repository) }
                onNodeWithContentDescription("Buscar terreno").assertDoesNotExist()
            } finally {
                directory.toFile().deleteRecursively()
            }
        }
}
