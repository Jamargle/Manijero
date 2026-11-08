package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.chat.ChatHomeScreen
import com.jamarglex.manijero.inspector.AnswerInspectorScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test

/** Pixel regression captures for the shared chat home screen in light and dark appearance. */
class ChatHomeScreenshotsTest : ScreenshotTestSupport() {
    private companion object {
        const val INSPECTOR_HEIGHT = 1600
    }

    /** Chat home in light appearance, before any question: the default entry surface. */
    @Test
    fun chatHomeIdleLight() =
        capture(name = "chat_home_idle_light", width = CHAT_WIDTH, height = CHAT_HEIGHT) {
            ManijeroTheme(darkTheme = false) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.idleChat,
                    onAction = {},
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
                    onRetentionInfoClick = {},
                )
            }
        }

    /** `Ayúdanos a mejorar` on: the switch row is replaced by the one small reminder line. */
    @Test
    fun chatHomeSavingOnLightPhone() =
        capture(name = "chat_home_saving_on_light_phone", width = PHONE_WIDTH, height = PHONE_HEIGHT) {
            ManijeroTheme(darkTheme = false) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.idleChat.copy(retainQuestions = true),
                    onAction = {},
                    onRetentionInfoClick = {},
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
                )
            }
        }

    /** The answered chat after a confirmed `Útil`: the thank-you row replaces the two controls. */
    @Test
    fun chatFeedbackSentDark() =
        capture(name = "chat_feedback_sent_dark", width = CHAT_WIDTH, height = CHAT_HEIGHT) {
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
        capture(name = "chat_abstention_dark", width = CHAT_WIDTH, height = CHAT_HEIGHT) {
            ManijeroTheme(darkTheme = true) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.abstainedResponse,
                    onAction = {},
                )
            }
        }

    /** A local test build's answered entry with the `Inspeccionar` link below the source card. */
    @Test
    fun chatAnsweredInspectLinkLight() =
        capture(name = "chat_answered_inspect_link_light", width = CHAT_WIDTH, height = CHAT_HEIGHT) {
            ManijeroTheme(darkTheme = false) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.answeredInspectedChat,
                    onAction = {},
                    onInspect = {},
                )
            }
        }

    /** A local test build's abstention with the `Inspeccionar` link below the caution card. */
    @Test
    fun chatAbstentionInspectLinkDark() =
        capture(name = "chat_abstention_inspect_link_dark", width = CHAT_WIDTH, height = CHAT_HEIGHT) {
            ManijeroTheme(darkTheme = true) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.abstainedInspectedChat,
                    onAction = {},
                    onInspect = {},
                )
            }
        }

    /** The inspector for an answered question, light appearance. */
    @Test
    fun inspectorAnsweredLight() =
        capture(name = "inspector_answered_light", width = CHAT_WIDTH, height = INSPECTOR_HEIGHT) {
            ManijeroTheme(darkTheme = false) {
                AnswerInspectorScreen(inspection = ScreenshotFixtures.answeredInspection, onBack = {})
            }
        }

    /** The inspector at phone width with 2x text, dark appearance: the compact case. */
    @Test
    fun inspectorPhoneLargeTextDark() =
        capture(
            name = "inspector_phone_large_text_dark",
            width = PHONE_WIDTH,
            height = PHONE_HEIGHT,
            fontScale = 2f,
        ) {
            ManijeroTheme(darkTheme = true) {
                AnswerInspectorScreen(inspection = ScreenshotFixtures.abstainedInspection, onBack = {})
            }
        }

    /** The clarification chooser over the two saved lands, light appearance. */
    @Test
    fun chatClarificationLight() =
        capture(name = "chat_clarification_light", width = CHAT_WIDTH, height = CHAT_HEIGHT) {
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
        capture(name = "chat_home_welcome_light", width = CHAT_WIDTH, height = CHAT_HEIGHT) {
            ManijeroTheme(darkTheme = false) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.idleChat,
                    onAction = {},
                    showWelcome = true,
                )
            }
        }

    /** The welcome card at phone width, 2x text, dark appearance. */
    @Test
    fun chatHomeWelcomePhoneLargeTextDark() =
        capture(
            name = "chat_home_welcome_phone_large_text_dark",
            width = PHONE_WIDTH,
            height = PHONE_HEIGHT,
            fontScale = 2f,
        ) {
            ManijeroTheme(darkTheme = true) {
                ChatHomeScreen(
                    state = ScreenshotFixtures.idleChat,
                    onAction = {},
                    showWelcome = true,
                )
            }
        }
}
