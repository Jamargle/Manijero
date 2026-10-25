package com.jamarglex.manijero.screenshots

import androidx.compose.runtime.Composable
import com.jamarglex.manijero.coverage.CoverageScreen
import com.jamarglex.manijero.privacy.PrivacyScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test

/** Dedicated informational-screen captures; host renders are not device/accessibility evidence. */
class HelpPrivacyScreenshotsTest : ScreenshotTestSupport() {
    @Test fun coverageLight() = capture("coverage_light", 900, 1200) { ManijeroTheme(darkTheme = false) { CoverageScreen({}) } }
    @Test fun coverageDark() = capture("coverage_dark", 900, 1200) { ManijeroTheme(darkTheme = true) { CoverageScreen({}) } }
    @Test fun privacyLight() = capture("privacy_light", 900, 1600) { ManijeroTheme(darkTheme = false) { PrivacyScreen(onBack = {}) } }
    @Test fun privacyDark() = capture("privacy_dark", 900, 1600) { ManijeroTheme(darkTheme = true) { PrivacyScreen(onBack = {}) } }

    @Test fun coveragePhoneLight() = capture("coverage_phone_light", PHONE_WIDTH, PHONE_HEIGHT) { ManijeroTheme(darkTheme = false) { CoverageScreen({}) } }
    @Test fun coveragePhoneDark() = capture("coverage_phone_dark", PHONE_WIDTH, PHONE_HEIGHT) { ManijeroTheme(darkTheme = true) { CoverageScreen({}) } }
    @Test fun privacyPhoneLight() = capture("privacy_phone_light", PHONE_WIDTH, PHONE_HEIGHT) { ManijeroTheme(darkTheme = false) { PrivacyScreen(onBack = {}) } }
    @Test fun privacyPhoneDark() = capture("privacy_phone_dark", PHONE_WIDTH, PHONE_HEIGHT) { ManijeroTheme(darkTheme = true) { PrivacyScreen(onBack = {}) } }

    @Test fun coveragePhoneLargeTextLight() = captureLargeText("coverage_phone_large_text_light", false) { CoverageScreen({}) }
    @Test fun coveragePhoneLargeTextDark() = captureLargeText("coverage_phone_large_text_dark", true) { CoverageScreen({}) }
    @Test fun privacyPhoneLargeTextLight() = captureLargeText("privacy_phone_large_text_light", false) { PrivacyScreen(onBack = {}) }
    @Test fun privacyPhoneLargeTextDark() = captureLargeText("privacy_phone_large_text_dark", true) { PrivacyScreen(onBack = {}) }

    private fun captureLargeText(name: String, darkTheme: Boolean, content: @Composable () -> Unit) =
        capture(name, PHONE_WIDTH, PHONE_HEIGHT, fontScale = 2f) {
            ManijeroTheme(darkTheme = darkTheme) { content() }
        }
}
