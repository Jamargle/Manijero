package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.ic_chat
import manijero.shared.generated.resources.ic_help
import manijero.shared.generated.resources.ic_lands
import org.jetbrains.compose.resources.DrawableResource

/**
 * One navigation destination: the caller's visible [label] and its shared brand [icon].
 *
 * It deliberately carries no `selected` flag: selection is the caller's `selectedIndex` resolved by
 * [selectedDestinationIndex], so a bar cannot disagree with the screen state that drives it.
 */
internal data class ManijeroDestination(
    val label: String,
    val icon: DrawableResource,
)

/**
 * Resolves the caller's requested destination index against the destination count: a valid index
 * is returned unchanged, anything else (negative, equal to the count, beyond it, or an empty bar)
 * resolves to -1, which selects nothing and never throws. Pure, so the boundary is unit-tested.
 */
internal fun selectedDestinationIndex(destinationsCount: Int, requestedIndex: Int): Int =
    if (requestedIndex in 0 until destinationsCount) requestedIndex else -1

/**
 * The bottom navigation bar for compact layouts: every destination shows its label and icon,
 * the selected item carries the Material indicator pill and a heavier label, and the targets stay
 * at Material's 48 dp minimum.
 *
 * No window insets are applied here; the shell's `Scaffold` is the single inset owner.
 */
@Composable
internal fun ManijeroBottomNavigation(
    destinations: List<ManijeroDestination>,
    selectedIndex: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val selected = selectedDestinationIndex(destinations.size, selectedIndex)
    NavigationBar(
        modifier = modifier.fillMaxWidth(),
        containerColor = MaterialTheme.colorScheme.surfaceContainerLowest,
        contentColor = MaterialTheme.colorScheme.onSurface,
        windowInsets = WindowInsets(0),
    ) {
        destinations.forEachIndexed { index, destination ->
            val isSelected = index == selected
            NavigationBarItem(
                selected = isSelected,
                onClick = { onSelect(index) },
                icon = {
                    ManijeroIcon(
                        resource = destination.icon,
                        contentDescription = null,
                    )
                },
                label = { Text(text = destination.label, fontWeight = navigationLabelWeight(isSelected)) },
                alwaysShowLabel = true,
            )
        }
    }
}

/**
 * The wide-layout navigation rail: the same destinations with their labels always visible, the
 * selected item marked by the indicator plus a heavier label, Material's minimum target, and no
 * window insets.
 */
@Composable
internal fun ManijeroNavigationRail(
    destinations: List<ManijeroDestination>,
    selectedIndex: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val selected = selectedDestinationIndex(destinations.size, selectedIndex)
    NavigationRail(
        modifier = modifier,
        containerColor = MaterialTheme.colorScheme.surfaceContainerLowest,
        contentColor = MaterialTheme.colorScheme.onSurface,
        windowInsets = WindowInsets(0),
    ) {
        destinations.forEachIndexed { index, destination ->
            val isSelected = index == selected
            NavigationRailItem(
                selected = isSelected,
                onClick = { onSelect(index) },
                icon = {
                    ManijeroIcon(
                        resource = destination.icon,
                        contentDescription = null,
                    )
                },
                label = { Text(text = destination.label, fontWeight = navigationLabelWeight(isSelected)) },
                alwaysShowLabel = true,
            )
        }
    }
}

/** Selection is never colour alone: the selected destination also gains a heavier label. */
private fun navigationLabelWeight(isSelected: Boolean): FontWeight =
    if (isSelected) FontWeight.SemiBold else FontWeight.Normal

private val previewDestinations = listOf(
    ManijeroDestination(label = "Asistente", icon = Res.drawable.ic_chat),
    ManijeroDestination(label = "Mis terrenos", icon = Res.drawable.ic_lands),
    ManijeroDestination(label = "Ayuda", icon = Res.drawable.ic_help),
)

@Composable
private fun ManijeroNavigationPreviewFrame(dark: Boolean) {
    ManijeroTheme(darkTheme = dark) {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ManijeroSpacing.Small),
                verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Medium),
            ) {
                ManijeroBottomNavigation(
                    destinations = previewDestinations,
                    selectedIndex = 0,
                    onSelect = {},
                )
                ManijeroNavigationRail(
                    destinations = previewDestinations,
                    selectedIndex = 1,
                    onSelect = {},
                )
            }
        }
    }
}

@Preview(name = "ManijeroNavigation — claro", widthDp = 380)
@Composable
private fun ManijeroNavigationLightPreview() = ManijeroNavigationPreviewFrame(dark = false)

@Preview(name = "ManijeroNavigation — oscuro", widthDp = 380)
@Composable
private fun ManijeroNavigationDarkPreview() = ManijeroNavigationPreviewFrame(dark = true)

@Preview(name = "ManijeroNavigation — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun ManijeroNavigationLargeTextPreview() = ManijeroNavigationPreviewFrame(dark = false)
