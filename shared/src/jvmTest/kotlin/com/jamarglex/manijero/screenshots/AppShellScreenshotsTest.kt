package com.jamarglex.manijero.screenshots

import androidx.compose.runtime.Composable
import com.jamarglex.manijero.AppSection
import com.jamarglex.manijero.AppShell
import com.jamarglex.manijero.chat.ChatHomeScreen
import com.jamarglex.manijero.settings.SettingsScreen
import com.jamarglex.manijero.coverage.CoverageScreen
import com.jamarglex.manijero.design.ManijeroTopBarMenuItem
import com.jamarglex.manijero.design.ManijeroTopBarSearch
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
        capture(name = "app_shell_settings_rail_light", width = 900, height = LAND_HEIGHT) {
            ManijeroTheme(darkTheme = false) { SettingsShell() }
        }

    @Test
    fun appShellHelpCompactWithUpArrow() =
        capture(
            name = "app_shell_help_compact_up_light",
            width = PHONE_WIDTH,
            height = PHONE_HEIGHT,
        ) {
            ManijeroTheme(darkTheme = false) { HelpDetailShell() }
        }

    @Test
    fun appShellLandsSearchOpenCompact() =
        capture(
            name = "app_shell_lands_search_open_light",
            width = PHONE_WIDTH,
            height = PHONE_HEIGHT,
        ) {
            ManijeroTheme(darkTheme = false) { LandsShell(searchOpen = true) }
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
    ShellFrame(
        AppSection.Assistant,
        menuItems = listOf(ManijeroTopBarMenuItem("Privacidad y ayuda", onClick = {})),
    ) {
        ChatHomeScreen(state = ScreenshotFixtures.idleChat, onAction = {})
    }
}

@Composable
private fun LandsShell(searchOpen: Boolean = false) {
    ShellFrame(
        AppSection.Lands,
        search = ManijeroTopBarSearch(
            open = searchOpen,
            query = if (searchOpen) "loma" else "",
            label = "Buscar terreno",
            hint = "Buscar por nombre, municipio o tipo…",
            clearDescription = "Borrar la búsqueda",
            closeDescription = "Cerrar la búsqueda",
            onOpen = {},
            onClose = {},
            onQueryChange = {},
        ),
    ) {
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
private fun SettingsShell() {
    ShellFrame(AppSection.Settings) {
        SettingsScreen(onOpenHelp = {}, improvementEnabled = false, onImprovementChange = {}, onOpenBackup = {})
    }
}

@Composable
private fun HelpDetailShell() {
    ShellFrame(AppSection.Settings, onBack = {}, screenTitle = "Qué puedes preguntar", tabsVisible = false) {
        CoverageScreen(onPrivacyClick = {}, onBack = {})
    }
}

@Composable
private fun ShellFrame(
    section: AppSection,
    onBack: (() -> Unit)? = null,
    menuItems: List<ManijeroTopBarMenuItem> = emptyList(),
    screenTitle: String? = null,
    tabsVisible: Boolean = true,
    search: ManijeroTopBarSearch? = null,
    content: @Composable () -> Unit,
) {
    AppShell(
        selectedSection = section,
        landsAvailable = true,
        navigationVisible = tabsVisible,
        onSectionSelect = {},
        onBack = onBack,
        screenTitle = screenTitle,
        search = search,
        menuItems = menuItems,
        content = content,
    )
}
