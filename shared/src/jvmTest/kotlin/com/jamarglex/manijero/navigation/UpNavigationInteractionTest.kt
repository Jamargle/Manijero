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

/** The top bar's up arrow: absent on tab screens, present on detail routes, and it goes back. */
@OptIn(ExperimentalTestApi::class)
class UpNavigationInteractionTest {
    @Test
    fun theUpArrowAppearsOnDetailRoutesAndReturnsToTheParent() =
        runDesktopComposeUiTest(width = 400, height = 2400) {
            setContent { App() }

            onNodeWithContentDescription("Volver").assertDoesNotExist()
            onNodeWithText("Ajustes").performClick()
            onNodeWithContentDescription("Volver").assertDoesNotExist()

            onNodeWithText("Ayuda").performClick()
            onNodeWithText("Qué puedes preguntar").assertExists()
            onNodeWithContentDescription("Volver").assertHeightIsAtLeast(48.dp).performClick()

            onNodeWithText("Qué puedes preguntar").assertDoesNotExist()
            onNodeWithText("Ayúdanos a mejorar").assertExists()
            onNodeWithContentDescription("Volver").assertDoesNotExist()
        }
}
