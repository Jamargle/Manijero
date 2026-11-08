package com.jamarglex.manijero.welcome

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import com.jamarglex.manijero.App
import kotlin.test.Test
import kotlin.test.assertEquals

@OptIn(ExperimentalTestApi::class)
class WelcomeFlowInteractionTest {
    private class FakeStore : WelcomeNoticeStore {
        var dismissed = false
        var writes = 0
        override fun isDismissed() = dismissed
        override fun markDismissed() {
            writes++
            dismissed = true
        }
    }

    private val title = "Antes de empezar"

    @Test
    fun cardShowsKeepsOneHeadingAndDismissalIsWrittenOnce() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            val store = FakeStore()
            setContent { App(welcomeNotice = store) }

            onNodeWithText(title).assertExists()
            onNodeWithContentDescription("Preguntar").assertExists()
            val headings = onAllNodes(SemanticsMatcher.keyIsDefined(SemanticsProperties.Heading))
            assertEquals(1, headings.fetchSemanticsNodes().size)

            onNodeWithText("Entendido").performScrollTo().performClick()
            onNodeWithText(title).assertDoesNotExist()
            assertEquals(1, store.writes)
        }

    @Test
    fun aNewAppOnTheSameStoreShowsNoCard() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            val store = FakeStore().apply { dismissed = true }
            setContent { App(welcomeNotice = store) }
            onNodeWithText(title).assertDoesNotExist()
        }

    @Test
    fun verBienvenidaShowsTheCardAgainWithoutWriting() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            val store = FakeStore().apply { dismissed = true }
            setContent { App(welcomeNotice = store) }

            onNodeWithText("Ajustes").performClick()
            onNodeWithText("Ayuda").performClick()
            onNodeWithText("Ver bienvenida").performScrollTo().performClick()
            onNodeWithText(title).assertExists()
            assertEquals(0, store.writes)

            onNodeWithText("Entendido").performScrollTo().performClick()
            onNodeWithText(title).assertDoesNotExist()
        }

    @Test
    fun withoutAStoreThereIsNeitherCardNorLink() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            setContent { App() }
            onNodeWithText(title).assertDoesNotExist()
            onNodeWithText("Ajustes").performClick()
            onNodeWithText("Ayuda").performClick()
            onNodeWithText("Ver bienvenida").assertDoesNotExist()
        }
}
