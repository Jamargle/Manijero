package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.coverage.CoverageScreen
import com.jamarglex.manijero.privacy.PrivacyScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Dedicated informational-screen captures rendered by Robolectric, not a real device. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "es-rES-w900dp-h1600dp-mdpi")
class HelpPrivacyAndroidScreenshotsTest : AndroidScreenshotTestSupport() {
    @Test fun coverageLight() = capture("coverage_light") { ManijeroTheme(darkTheme = false) { CoverageScreen({}) } }
    @Test fun coverageDark() = capture("coverage_dark") { ManijeroTheme(darkTheme = true) { CoverageScreen({}) } }
    @Test fun privacyLight() = capture("privacy_light") { ManijeroTheme(darkTheme = false) { PrivacyScreen(onBack = {}) } }
    @Test fun privacyDark() = capture("privacy_dark") { ManijeroTheme(darkTheme = true) { PrivacyScreen(onBack = {}) } }

    @Test
    @Config(qualifiers = "es-rES-w360dp-h800dp-mdpi")
    fun coveragePhoneLight() = capture("coverage_phone_light") { ManijeroTheme(darkTheme = false) { CoverageScreen({}) } }

    @Test
    @Config(qualifiers = "es-rES-w360dp-h800dp-mdpi")
    fun coveragePhoneDark() = capture("coverage_phone_dark") { ManijeroTheme(darkTheme = true) { CoverageScreen({}) } }

    @Test
    @Config(qualifiers = "es-rES-w360dp-h800dp-mdpi")
    fun privacyPhoneLight() = capture("privacy_phone_light") { ManijeroTheme(darkTheme = false) { PrivacyScreen(onBack = {}) } }

    @Test
    @Config(qualifiers = "es-rES-w360dp-h800dp-mdpi")
    fun privacyPhoneDark() = capture("privacy_phone_dark") { ManijeroTheme(darkTheme = true) { PrivacyScreen(onBack = {}) } }

    @Test
    @Config(qualifiers = "es-rES-w360dp-h800dp-mdpi")
    fun coveragePhoneLargeTextLight() = capture("coverage_phone_large_text_light", fontScale = 2f) {
        ManijeroTheme(darkTheme = false) { CoverageScreen({}) }
    }

    @Test
    @Config(qualifiers = "es-rES-w360dp-h800dp-mdpi")
    fun coveragePhoneLargeTextDark() = capture("coverage_phone_large_text_dark", fontScale = 2f) {
        ManijeroTheme(darkTheme = true) { CoverageScreen({}) }
    }

    @Test
    @Config(qualifiers = "es-rES-w360dp-h800dp-mdpi")
    fun privacyPhoneLargeTextLight() = capture("privacy_phone_large_text_light", fontScale = 2f) {
        ManijeroTheme(darkTheme = false) { PrivacyScreen(onBack = {}) }
    }

    @Test
    @Config(qualifiers = "es-rES-w360dp-h800dp-mdpi")
    fun privacyPhoneLargeTextDark() = capture("privacy_phone_large_text_dark", fontScale = 2f) {
        ManijeroTheme(darkTheme = true) { PrivacyScreen(onBack = {}) }
    }
}
