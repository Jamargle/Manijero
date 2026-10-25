package com.jamarglex.manijero.chat

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import com.jamarglex.manijero.ChatHomeAction
import com.jamarglex.manijero.ChatHomeState
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Permanent interaction coverage for the assistant surface. It complements the screenshot suite:
 * the goldens prove the layout, this test proves that the visible controls keep their behavior
 * after the restyle. It runs on the existing Compose Desktop test target (no device, no Robolectric)
 * and is part of `:shared:jvmTest`.
 *
 * What it checks: the send action cannot fire on a blank question; a suggested question fills the
 * composer through the callback and never submits; and `Reintentar` is a separate, enabled control
 * that emits `RetryClicked`. It does not prove screen-reader output, pointer size, or visual quality.
 */
@OptIn(ExperimentalTestApi::class)
class ChatHomeInteractionTest {

    @Test
    fun sendIsDisabledWhileTheQuestionIsBlank() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(state = ChatHomeState(), onAction = {})
                }
            }

            onNodeWithText("Preguntar").performScrollTo().assertIsNotEnabled()
        }

    @Test
    fun suggestedQuestionFillsTheComposerWithoutSubmitting() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            val actions = mutableListOf<ChatHomeAction>()
            var state by mutableStateOf(ChatHomeState())
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(
                        state = state,
                        onAction = { action ->
                            actions += action
                            when (action) {
                                is ChatHomeAction.QuestionChanged ->
                                    state = state.copy(question = action.value)

                                is ChatHomeAction.SuggestedQuestionSelected ->
                                    state = state.copy(question = action.question)

                                else -> Unit
                            }
                        },
                    )
                }
            }

            val question = "¿Qué es el SIGPAC y para qué sirve?"
            onNodeWithText(question).performScrollTo().performClick()

            assertEquals(listOf<ChatHomeAction>(ChatHomeAction.SuggestedQuestionSelected(question)), actions)
            assertEquals(question, state.question)
        }

    @Test
    fun retryIsASeparateEnabledControl() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            val actions = mutableListOf<ChatHomeAction>()
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(
                        state = ChatHomeState(
                            failure = RequestFailure.SERVICE_ERROR,
                            failedQuestion = "¿Puedo regar hoy?",
                        ),
                        onAction = { action -> actions += action },
                    )
                }
            }

            onNodeWithText("Reintentar").performScrollTo().assertIsEnabled().performClick()

            assertEquals(listOf<ChatHomeAction>(ChatHomeAction.RetryClicked), actions)
        }
}
