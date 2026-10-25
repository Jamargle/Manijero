package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.ChatHomeScreen
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
                    onLandsClick = {},
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
                    onLandsClick = {},
                    onPrivacyClick = {},
                    onCoverageClick = {},
                )
            }
        }
}
