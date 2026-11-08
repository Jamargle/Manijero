package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.chat.ChatHomeScreen
import com.jamarglex.manijero.inspector.AnswerInspectorScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Pixel regression captures for the shared chat home screen, rendered by Android via Robolectric. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "es-rES-w360dp-h800dp-mdpi")
class ChatHomeAndroidScreenshotsTest : AndroidScreenshotTestSupport() {

    /** Chat home in light appearance, before any question: the default entry surface. */
    @Test
    fun chatHomeIdleLight() =
        capture("chat_home_idle_light") {
            ManijeroTheme(darkTheme = false) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.idleChat,
                    onAction = {},
                )
            }
        }

    /**
     * Dark appearance of the densest chat state: a supported answer, scope caption, source card.
     * On the phone viewport the frame records the top of the page; the composer is below the fold.
     */
    @Test
    fun chatAnsweredSourceDark() =
        capture("chat_answered_source_dark") {
            ManijeroTheme(darkTheme = true) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.answeredChat,
                    onAction = {},
                )
            }
        }

    /** The answered chat after a confirmed `Útil`: the thank-you row replaces the two controls. */
    @Test
    fun chatFeedbackSentDark() =
        capture("chat_feedback_sent_dark") {
            ManijeroTheme(darkTheme = true) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.answeredFeedbackSent,
                    onAction = {},
                )
            }
        }

    /** The caution abstention: icon, speaker, scope, state label and the server message verbatim. */
    @Test
    fun chatAbstentionDark() =
        capture("chat_abstention_dark") {
            ManijeroTheme(darkTheme = true) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.abstainedResponse,
                    onAction = {},
                )
            }
        }

    /** A local test build's answered entry with the `Inspeccionar` link. */
    @Test
    fun chatAnsweredInspectLinkLight() =
        capture("chat_answered_inspect_link_light") {
            ManijeroTheme(darkTheme = false) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.answeredInspectedChat,
                    onAction = {},
                    onInspect = {},
                )
            }
        }

    /** A local test build's abstention with the `Inspeccionar` link. */
    @Test
    fun chatAbstentionInspectLinkDark() =
        capture("chat_abstention_inspect_link_dark") {
            ManijeroTheme(darkTheme = true) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.abstainedInspectedChat,
                    onAction = {},
                    onInspect = {},
                )
            }
        }

    /** The inspector with 2x text, dark appearance. */
    @Test
    fun inspectorLargeTextDark() =
        capture("inspector_large_text_dark", fontScale = 2f) {
            ManijeroTheme(darkTheme = true) {
                AnswerInspectorScreen(inspection = ScreenshotFixtures.answeredInspection, onBack = {})
            }
        }

    /** The clarification chooser over the two saved lands, light appearance. */
    @Test
    fun chatClarificationLight() =
        capture("chat_clarification_light") {
            ManijeroTheme(darkTheme = false) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.clarificationChat,
                    onAction = {},
                    clarificationLands = ScreenshotFixtures.twoLands.lands,
                )
            }
        }

    /** First use: the welcome card above the hero, light appearance. */
    @Test
    fun chatHomeWelcomeLight() =
        capture("chat_home_welcome_light") {
            ManijeroTheme(darkTheme = false) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.idleChat,
                    onAction = {},
                    showWelcome = true,
                )
            }
        }
}
