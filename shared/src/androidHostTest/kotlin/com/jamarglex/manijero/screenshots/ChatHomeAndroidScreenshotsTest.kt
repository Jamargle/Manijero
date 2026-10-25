package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.chat.ChatHomeScreen
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
                    onPrivacyClick = {},
                    onCoverageClick = {},
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
                    onPrivacyClick = {},
                    onCoverageClick = {},
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
                    onPrivacyClick = {},
                    onCoverageClick = {},
                )
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
}
