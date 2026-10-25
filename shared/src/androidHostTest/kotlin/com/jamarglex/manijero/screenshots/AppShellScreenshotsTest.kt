package com.jamarglex.manijero.screenshots

import androidx.compose.runtime.Composable
import com.jamarglex.manijero.AppSection
import com.jamarglex.manijero.AppShell
import com.jamarglex.manijero.ChatHomeScreen
import com.jamarglex.manijero.coverage.CoverageScreen
import com.jamarglex.manijero.lands.LandListScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Pixel regression captures for the app shell as Android renders it through Robolectric. The
 * compact captures use the class viewport; the two rail captures override it per method, because
 * the wide layout replaces the bottom bar with the labelled rail at 840 dp.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "es-rES-w360dp-h800dp-mdpi")
class AppShellScreenshotsTest : AndroidScreenshotTestSupport() {

    @Test
    fun appShellAssistantCompactLight() =
        capture("app_shell_assistant_compact_light") {
            ManijeroTheme(darkTheme = false) { AssistantShell() }
        }

    @Test
    @Config(qualifiers = "es-rES-w900dp-h1000dp-mdpi")
    fun appShellLandsRailDark() =
        capture("app_shell_lands_rail_dark") {
            ManijeroTheme(darkTheme = true) { LandsShell() }
        }

    @Test
    @Config(qualifiers = "es-rES-w900dp-h1000dp-mdpi")
    fun appShellHelpRailLight() =
        capture("app_shell_help_rail_light") {
            ManijeroTheme(darkTheme = false) { HelpShell() }
        }

    @Test
    fun appShellAssistantCompactLargeText() =
        capture("app_shell_assistant_compact_large_text", fontScale = 2f) {
            ManijeroTheme(darkTheme = false) { AssistantShell() }
        }
}

@Composable
private fun AssistantShell() {
    ShellFrame(AppSection.Assistant) {
        ChatHomeScreen(state = ScreenshotFixtures.idleChat, onAction = {})
    }
}

@Composable
private fun LandsShell() {
    ShellFrame(AppSection.Lands) {
        LandListScreen(
            state = ScreenshotFixtures.twoLands,
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Composable
private fun HelpShell() {
    ShellFrame(AppSection.Help) {
        CoverageScreen(onPrivacyClick = {})
    }
}

@Composable
private fun ShellFrame(section: AppSection, content: @Composable () -> Unit) {
    AppShell(
        selectedSection = section,
        landsAvailable = true,
        navigationVisible = true,
        onSectionSelect = {},
        content = content,
    )
}
