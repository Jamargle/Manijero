package com.jamarglex.manijero.chat

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.hasAnyAncestor
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertIsOff
import androidx.compose.ui.test.assertIsOn
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isToggleable
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.AnswerFeedback
import com.jamarglex.manijero.ChatHomeAction
import com.jamarglex.manijero.ChatHomeState
import com.jamarglex.manijero.ChatMessage
import com.jamarglex.manijero.Speaker
import com.jamarglex.manijero.chat.AnswerRating
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.screenshots.ScreenshotFixtures
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

            onNodeWithContentDescription("Preguntar").performScrollTo().assertIsNotEnabled()
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
    fun inspectLinkShowsOnlyOnAnsweredAndAbstainedEntriesWithAnInspection() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            val inspected = mutableListOf<ChatMessage>()
            var state by mutableStateOf(ScreenshotFixtures.answeredInspectedChat)
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(state = state, onAction = {}, onInspect = { inspected += it })
                }
            }

            onNodeWithText("Inspeccionar").performScrollTo().assertHasClickAction()
            // Its own node: never inside the entry's merged, politely announced live region.
            onAllNodes(
                hasText("Inspeccionar") and
                    hasAnyAncestor(SemanticsMatcher.expectValue(SemanticsProperties.LiveRegion, LiveRegionMode.Polite)),
            ).assertCountEquals(0)
            onNodeWithText("Inspeccionar").performClick()
            assertEquals(
                listOf(ScreenshotFixtures.answeredInspectedChat.messages.last()),
                inspected,
            )

            state = ScreenshotFixtures.abstainedInspectedChat
            onAllNodesWithText("Inspeccionar").assertCountEquals(1)

            state = ScreenshotFixtures.answeredChat
            onAllNodesWithText("Inspeccionar").assertCountEquals(0)
            state = ScreenshotFixtures.abstainedResponse
            onAllNodesWithText("Inspeccionar").assertCountEquals(0)
        }

    @Test
    fun inspectLinkNeverShowsWithoutTheCallback() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(state = ScreenshotFixtures.answeredInspectedChat, onAction = {})
                }
            }

            onAllNodesWithText("Inspeccionar").assertCountEquals(0)
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

    @Test
    fun retentionChoiceIsUncheckedSeparateAndNeverSubmits() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            val actions = mutableListOf<ChatHomeAction>()
            var state by mutableStateOf(ChatHomeState(question = "¿Puedo regar hoy?"))
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(
                        state = state,
                        onAction = { action ->
                            actions += action
                            if (action is ChatHomeAction.RetentionChoiceChanged) {
                                state = state.copy(retainNextQuestion = action.allowed)
                            }
                        },
                    )
                }
            }

            val label = "Permitir guardar esta pregunta y su respuesta para mejorar Manijero"
            onNode(hasText(label) and isToggleable()).performScrollTo().assertIsOff().performClick()

            assertEquals(listOf<ChatHomeAction>(ChatHomeAction.RetentionChoiceChanged(true)), actions)
            onNode(hasText(label) and isToggleable()).assertIsOn()
            onNodeWithText("se borra sola en 30 días como máximo", substring = true).assertExists()
            onNodeWithContentDescription("Preguntar").assertIsEnabled()
        }

    @Test
    fun feedbackControlsShowUnderEveryFinishedAnswerAndNowhereElse() =
        runDesktopComposeUiTest(width = 900, height = 1600) {
            var state by mutableStateOf(ScreenshotFixtures.answeredChat)
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(state = state, onAction = {})
                }
            }

            // A supported answer: both named controls, each with the accepted 48 dp target.
            onAllNodesWithText("Útil").assertCountEquals(1)
            onAllNodesWithText("No útil").assertCountEquals(1)
            onNodeWithText("Útil").performScrollTo().assertIsEnabled().assertHeightIsAtLeast(48.dp)
            onNodeWithText("No útil").assertIsEnabled().assertHeightIsAtLeast(48.dp)

            // An abstention is a decoded answer too.
            state = ScreenshotFixtures.abstainedResponse
            onAllNodesWithText("Útil").assertCountEquals(1)
            onAllNodesWithText("No útil").assertCountEquals(1)

            // Nothing else on the surface offers a rating.
            state = ScreenshotFixtures.idleChat
            onAllNodesWithText("Útil").assertCountEquals(0)
            onAllNodesWithText("No útil").assertCountEquals(0)
            state = ScreenshotFixtures.clarificationChat
            onAllNodesWithText("Útil").assertCountEquals(0)
            onAllNodesWithText("No útil").assertCountEquals(0)
            state = ChatHomeState(messages = listOf(ChatMessage(Speaker.USER, "¿Puedo regar hoy?")))
            onAllNodesWithText("Útil").assertCountEquals(0)
            onAllNodesWithText("No útil").assertCountEquals(0)
        }

    @Test
    fun eachRatingTapEmitsTheFeedbackActionWithItsEntryIndex() =
        runDesktopComposeUiTest(width = 900, height = 1600) {
            val actions = mutableListOf<ChatHomeAction>()
            var state by mutableStateOf(
                ScreenshotFixtures.answeredChat.copy(
                    messages = ScreenshotFixtures.answeredChat.messages + ScreenshotFixtures.abstainedResponse.messages,
                ),
            )
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(state = state, onAction = { action -> actions += action })
                }
            }

            // Entry 1 is the answered reply, entry 3 the abstention: each sends its own index.
            onAllNodesWithText("Útil")[0].performScrollTo().performClick()
            assertEquals(listOf<ChatHomeAction>(ChatHomeAction.FeedbackClicked(1, AnswerRating.USEFUL)), actions)

            onAllNodesWithText("No útil")[1].performScrollTo().performClick()
            assertEquals(
                ChatHomeAction.FeedbackClicked(3, AnswerRating.NOT_USEFUL),
                actions.last(),
            )
            onNodeWithContentDescription("Preguntar").assertExists()
        }

    @Test
    fun theRatingControlsSitOutsideThePoliteLiveRegion() =
        runDesktopComposeUiTest(width = 900, height = 1600) {
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(state = ScreenshotFixtures.answeredChat, onAction = {})
                }
            }

            onAllNodes(
                (hasText("Útil") or hasText("No útil")) and
                    hasAnyAncestor(
                        SemanticsMatcher.expectValue(SemanticsProperties.LiveRegion, LiveRegionMode.Polite),
                    ),
            ).assertCountEquals(0)
        }

    @Test
    fun aSentRatingShowsTheThanksLineAndLeavesNothingToTap() =
        runDesktopComposeUiTest(width = 900, height = 1600) {
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(state = ScreenshotFixtures.answeredFeedbackSent, onAction = {})
                }
            }

            onNodeWithText("Gracias, tu respuesta nos ayuda a mejorar.")
                .performScrollTo()
                .assertExists()
            onAllNodesWithText("Útil").assertCountEquals(0)
            onAllNodesWithText("No útil").assertCountEquals(0)
            // The composer is untouched: it is still there with its own state.
            onNodeWithContentDescription("Preguntar").assertExists()
        }

    @Test
    fun aFailedRatingKeepsBothControlsEnabledAndShowsTheRetryLine() =
        runDesktopComposeUiTest(width = 900, height = 1600) {
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(state = answeredWith(AnswerFeedback.Failed(AnswerRating.USEFUL)), onAction = {})
                }
            }

            onNodeWithText("No se ha podido enviar tu valoración. Inténtalo otra vez.")
                .performScrollTo()
                .assertExists()
            onNodeWithText("Útil").assertIsEnabled()
            onNodeWithText("No útil").assertIsEnabled()
            onAllNodesWithText("Gracias, tu respuesta nos ayuda a mejorar.").assertCountEquals(0)
        }

    @Test
    fun anInFlightRatingDisablesBothControls() =
        runDesktopComposeUiTest(width = 900, height = 1600) {
            setContent {
                ManijeroTheme(darkTheme = false) {
                    ChatHomeScreen(state = answeredWith(AnswerFeedback.Sending(AnswerRating.USEFUL)), onAction = {})
                }
            }

            onNodeWithText("Útil").performScrollTo().assertIsNotEnabled()
            onNodeWithText("No útil").assertIsNotEnabled()
            onAllNodesWithText("Gracias, tu respuesta nos ayuda a mejorar.").assertCountEquals(0)
            onAllNodesWithText("No se ha podido enviar tu valoración. Inténtalo otra vez.").assertCountEquals(0)
        }

    @Test
    fun theRatingControlsWrapAtLargeTextInsteadOfClipping() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            setContent {
                CompositionLocalProvider(LocalDensity provides Density(density = 1f, fontScale = 2f)) {
                    ManijeroTheme(darkTheme = true) {
                        ChatHomeScreen(state = ScreenshotFixtures.answeredChat, onAction = {})
                    }
                }
            }

            // Both labels stay whole, named and tappable at 2x text.
            onNodeWithText("Útil").performScrollTo().assertIsEnabled().assertHeightIsAtLeast(48.dp)
            onNodeWithText("No útil").performScrollTo().assertIsEnabled().assertHeightIsAtLeast(48.dp)
        }

    private fun answeredWith(feedback: AnswerFeedback) = ScreenshotFixtures.answeredChat.copy(
        messages = ScreenshotFixtures.answeredChat.messages.map { message ->
            if (message.speaker == Speaker.ASSISTANT) message.copy(feedback = feedback) else message
        },
    )
}
