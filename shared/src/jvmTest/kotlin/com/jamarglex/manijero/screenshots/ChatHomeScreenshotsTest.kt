package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.ChatHomeScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test

/** Pixel regression captures for the shared chat home screen in light and dark appearance. */
class ChatHomeScreenshotsTest : ScreenshotTestSupport() {

    /** Chat home in light appearance, before any question: the default entry surface. */
    @Test
    fun chatHomeIdleLight() =
        capture(name = "chat_home_idle_light", width = CHAT_WIDTH, height = CHAT_HEIGHT) {
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

    /** Dark appearance of the densest chat state: a supported answer, scope caption, source card. */
    @Test
    fun chatAnsweredSourceDark() =
        capture(name = "chat_answered_source_dark", width = CHAT_WIDTH, height = CHAT_HEIGHT) {
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
