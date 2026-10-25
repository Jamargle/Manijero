package com.jamarglex.manijero.screenshots

import androidx.compose.runtime.Composable
import com.jamarglex.manijero.AppSection
import com.jamarglex.manijero.AppShell
import com.jamarglex.manijero.ChatHomeScreen
import com.jamarglex.manijero.coverage.CoverageScreen
import com.jamarglex.manijero.lands.LandListScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test

/**
 * Pixel regression captures for the app shell: the brand top app bar, the compact bottom bar, and
 * the wide labelled rail around the real shared screens. The fixtures are code-owned, so no store,
 * clock, network, or backend is involved.
 *
 * These are host renders, not device or screen-reader evidence. The goldens of the individual
 * screens stay in their own test classes; only the four shell frames are recorded here.
 */
class AppShellScreenshotsTest : ScreenshotTestSupport() {

    @Test
    fun appShellAssistantCompactLight() =
        capture(
            name = "app_shell_assistant_compact_light",
            width = PHONE_WIDTH,
            height = PHONE_HEIGHT,
        ) {
            ManijeroTheme(darkTheme = false) { AssistantShell() }
        }

    @Test
    fun appShellLandsRailDark() =
        capture(name = "app_shell_lands_rail_dark", width = 900, height = LAND_HEIGHT) {
            ManijeroTheme(darkTheme = true) { LandsShell() }
        }

    @Test
    fun appShellHelpRailLight() =
        capture(name = "app_shell_help_rail_light", width = 900, height = LAND_HEIGHT) {
            ManijeroTheme(darkTheme = false) { HelpShell() }
        }

    @Test
    fun appShellAssistantCompactLargeText() =
        capture(
            name = "app_shell_assistant_compact_large_text",
            width = PHONE_WIDTH,
            height = PHONE_HEIGHT,
            fontScale = 2f,
        ) {
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
