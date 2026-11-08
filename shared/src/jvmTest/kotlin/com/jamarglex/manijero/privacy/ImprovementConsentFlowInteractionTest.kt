package com.jamarglex.manijero.privacy

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsOff
import androidx.compose.ui.test.assertIsOn
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isToggleable
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import com.jamarglex.manijero.App
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * `Ayúdanos a mejorar` end to end in the app: the chat label opens `Ajustes`, the switch there and
 * the chat checkbox are one saved value, and a new app on the same store keeps it.
 */
@OptIn(ExperimentalTestApi::class)
class ImprovementConsentFlowInteractionTest {
    private class FakeStore : ImprovementConsentStore {
        var value = false
        val writes = mutableListOf<Boolean>()
        override fun isEnabled() = value
        override fun setEnabled(enabled: Boolean) {
            writes += enabled
            value = enabled
        }
    }

    private val checkbox = hasContentDescription("Ayúdanos a mejorar: guardar tus preguntas y respuestas") and isToggleable()
    private val switch = hasText("Guardar mis preguntas y respuestas para mejorar Manijero") and isToggleable()

    @Test
    fun theChatLinkOpensAjustesAndBothControlsShareOneSavedValue() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            val store = FakeStore()
            setContent { App(improvementConsent = store) }

            onNode(checkbox).assertIsOff()
            onNodeWithText("Ayúdanos a mejorar").performClick()

            onNodeWithText("Empieza desactivado", substring = true).assertExists()
            onNode(switch).performScrollTo().assertIsOff().performClick()
            onNode(switch).assertIsOn()
            assertEquals(listOf(true), store.writes)

            onNodeWithText("Asistente").performClick()
            onNode(checkbox).assertIsOn().performClick()
            onNode(checkbox).assertIsOff()
            assertEquals(listOf(true, false), store.writes)
        }

    @Test
    fun aSavedChoiceIsShownOnLaunch() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            val store = FakeStore().apply { value = true }
            setContent { App(improvementConsent = store) }
            onNode(checkbox).assertIsOn()
        }
}
