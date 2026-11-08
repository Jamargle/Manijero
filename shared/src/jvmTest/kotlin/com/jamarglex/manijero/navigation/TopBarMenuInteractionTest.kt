package com.jamarglex.manijero.navigation

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.App
import kotlin.test.Test

/**
 * The assistant's `⋮` menu: it holds `Privacidad y ayuda` and `Qué cubre la app` (no longer in the
 * chat footer), each item opens its screen, and the menu exists only on the assistant screen.
 */
@OptIn(ExperimentalTestApi::class)
class TopBarMenuInteractionTest {
    @Test
    fun theChatMenuOpensPrivacyAndCoverageAndIsOnlyOnTheAssistant() =
        runDesktopComposeUiTest(width = 400, height = 2400) {
            setContent { App() }

            // The links are no longer in the chat itself.
            onNodeWithText("Privacidad y ayuda").assertDoesNotExist()
            onNodeWithText("Qué cubre la app").assertDoesNotExist()

            onNodeWithContentDescription("Más opciones").assertHeightIsAtLeast(48.dp).performClick()
            onNodeWithText("Privacidad y ayuda").performClick()
            onNodeWithContentDescription("Más opciones").assertDoesNotExist()
            onNodeWithContentDescription("Volver").performClick()

            onNodeWithContentDescription("Más opciones").performClick()
            onNodeWithText("Qué cubre la app").performClick()
            onNodeWithText("Qué puedes preguntar").assertExists()
            onNodeWithContentDescription("Volver").performClick()
            onNodeWithContentDescription("Más opciones").assertExists()

            onNodeWithText("Ajustes").performClick()
            onNodeWithContentDescription("Más opciones").assertDoesNotExist()
        }
}
