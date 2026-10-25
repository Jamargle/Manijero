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
                    onPrivacyClick = {},
                    onCoverageClick = {},
                )
            }
        }

    /** The idle chat home at the single phone-width viewport, light appearance. */
    @Test
    fun chatHomeIdleLightPhone() =
        capture(name = "chat_home_idle_light_phone", width = PHONE_WIDTH, height = PHONE_HEIGHT) {
            ManijeroTheme(darkTheme = false) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.idleChat,
                    onAction = {},
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
                    onPrivacyClick = {},
                    onCoverageClick = {},
                )
            }
        }

    /**
     * The answered chat at the phone-width viewport, dark appearance. On this height the golden
     * records the top of the page (title, transcript, answer, and the start of the source card);
     * the composer below the fold is deliberately outside the frame.
     */
    @Test
    fun chatAnsweredSourceDarkPhone() =
        capture(
            name = "chat_answered_source_dark_phone",
            width = PHONE_WIDTH,
            height = PHONE_HEIGHT,
        ) {
            ManijeroTheme(darkTheme = true) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.answeredChat,
                    onAction = {},
                    onPrivacyClick = {},
                    onCoverageClick = {},
                )
            }
        }
}
