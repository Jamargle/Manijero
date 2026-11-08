package com.jamarglex.manijero

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.design.ManijeroBottomNavigation
import com.jamarglex.manijero.design.ManijeroDestination
import com.jamarglex.manijero.design.ManijeroNavigationRail
import com.jamarglex.manijero.design.ManijeroTopAppBar
import com.jamarglex.manijero.design.ManijeroTopBarMenuItem
import com.jamarglex.manijero.design.ManijeroTopBarSearch
import com.jamarglex.manijero.design.selectedDestinationIndex
import com.jamarglex.manijero.design.WideWindowBreakpoint
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.app_title
import manijero.shared.generated.resources.ic_chat
import manijero.shared.generated.resources.ic_settings
import manijero.shared.generated.resources.ic_lands
import manijero.shared.generated.resources.nav_assistant
import manijero.shared.generated.resources.nav_back
import manijero.shared.generated.resources.nav_more
import manijero.shared.generated.resources.nav_settings
import manijero.shared.generated.resources.nav_lands
import org.jetbrains.compose.resources.stringResource

/**
 * The one app frame: a flat brand top app bar, the selected screen, and either a bottom navigation
 * bar below [WideWindowBreakpoint] or a labelled navigation rail from it.
 *
 * The shell is the single window-inset owner. It paints the bar surfaces behind the status and
 * navigation bars, applies the ime inset so the bottom bar stays above the keyboard, and passes the
 * remaining scaffold padding to [content]. It owns the navigation copy and section callbacks; the
 * screens it hosts keep their own state, copy, padding and scroll.
 *
 * [search], when given, puts the magnifier (and, once opened, the search field) in the top bar; the
 * composition root passes it on `Mis terrenos` only.
 *
 * [screenTitle] is passed on detail routes only: the top bar then shows that title (and no brand
 * mark) and the screens drop their own large heading. Top-level tab screens keep the brand mark and
 * `Manijero`, because the selected tab already says where the person is.
 *
 * [menuItems], when not empty, fill the top bar's `⋮` menu (the composition root passes them on the
 * assistant screen only).
 *
 * [onBack], when given, shows the up arrow at the start of the top bar; the composition root passes
 * it on every detail route and the forms, and omits it on the three top-level tabs.
 *
 * When [navigationVisible] is false (a land form holds unsaved input) only the top app bar remains.
 * The top app bar's only right-side control is the assistant's `⋮` menu ([menuItems]); privacy
 * stays reachable from that menu and from the help screen under `Ajustes`.
 */
@Composable
internal fun AppShell(
    selectedSection: AppSection,
    landsAvailable: Boolean,
    navigationVisible: Boolean,
    onSectionSelect: (AppSection) -> Unit,
    modifier: Modifier = Modifier,
    onBack: (() -> Unit)? = null,
    menuItems: List<ManijeroTopBarMenuItem> = emptyList(),
    screenTitle: String? = null,
    search: ManijeroTopBarSearch? = null,
    content: @Composable () -> Unit,
) {
    val sections = availableSections(landsAvailable)
    val selectedIndex = selectedDestinationIndex(sections.size, sections.indexOf(selectedSection))
    val destinations = sections.map { section ->
        ManijeroDestination(
            label = stringResource(section.labelResource()),
            icon = section.iconResource(),
        )
    }
    val selectAt: (Int) -> Unit = { index ->
        sections.getOrNull(index)?.let(onSectionSelect)
    }

    BoxWithConstraints(modifier = modifier.fillMaxSize().imePadding()) {
        val wide = maxWidth >= WideWindowBreakpoint
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            containerColor = MaterialTheme.colorScheme.background,
            topBar = {
                Surface(color = MaterialTheme.colorScheme.surfaceContainerLowest) {
                    Column(modifier = Modifier.statusBarsPadding()) {
                        ManijeroTopAppBar(
                            title = screenTitle ?: stringResource(Res.string.app_title),
                            screenTitle = screenTitle != null,
                            onBack = onBack,
                            backDescription = stringResource(Res.string.nav_back),
                            menuItems = menuItems,
                            menuDescription = stringResource(Res.string.nav_more),
                            search = search,
                        )
                    }
                }
            },
            bottomBar = {
                if (navigationVisible && !wide) {
                    Surface(color = MaterialTheme.colorScheme.surfaceContainerLowest) {
                        Column(modifier = Modifier.navigationBarsPadding()) {
                            ManijeroBottomNavigation(
                                destinations = destinations,
                                selectedIndex = selectedIndex,
                                onSelect = selectAt,
                            )
                        }
                    }
                }
            },
        ) { innerPadding ->
            // The bar wrappers paint behind the status/navigation bars; Scaffold's default
            // system-bar insets then pad the content by the laid-out top/bottom bar height, or by
            // the system inset when a bar is absent (wide rail, land forms). That is the one place
            // the shell reserves space: the rail and the content share this padding.
            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
            ) {
                if (navigationVisible && wide) {
                    ManijeroNavigationRail(
                        destinations = destinations,
                        selectedIndex = selectedIndex,
                        onSelect = selectAt,
                    )
                }
                Box(modifier = Modifier.weight(1f)) {
                    content()
                }
            }
        }
    }
}

private fun AppSection.labelResource() = when (this) {
    AppSection.Assistant -> Res.string.nav_assistant
    AppSection.Lands -> Res.string.nav_lands
    AppSection.Settings -> Res.string.nav_settings
}

private fun AppSection.iconResource() = when (this) {
    AppSection.Assistant -> Res.drawable.ic_chat
    AppSection.Lands -> Res.drawable.ic_lands
    AppSection.Settings -> Res.drawable.ic_settings
}

// Preview sample only, never shipped copy.
@Composable
private fun AppShellPreviewFrame(
    selectedSection: AppSection,
    dark: Boolean,
) {
    ManijeroTheme(darkTheme = dark) {
        AppShell(
            selectedSection = selectedSection,
            landsAvailable = true,
            navigationVisible = true,
            onSectionSelect = {},
        ) {
            Text(
                text = "Contenido de la pantalla seleccionada.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onBackground,
                modifier = Modifier.padding(24.dp),
            )
        }
    }
}

@Preview(name = "AppShell compact — claro", widthDp = 400, heightDp = 640)
@Composable
private fun AppShellCompactLightPreview() =
    AppShellPreviewFrame(AppSection.Assistant, dark = false)

@Preview(name = "AppShell compact — oscuro", widthDp = 400, heightDp = 640)
@Composable
private fun AppShellCompactDarkPreview() =
    AppShellPreviewFrame(AppSection.Settings, dark = true)

@Preview(name = "AppShell ancho — claro", widthDp = 1000, heightDp = 700)
@Composable
private fun AppShellWideLightPreview() =
    AppShellPreviewFrame(AppSection.Lands, dark = false)

@Preview(name = "AppShell compact — texto grande", widthDp = 360, heightDp = 900, fontScale = 2f)
@Composable
private fun AppShellCompactLargeTextPreview() =
    AppShellPreviewFrame(AppSection.Assistant, dark = false)
