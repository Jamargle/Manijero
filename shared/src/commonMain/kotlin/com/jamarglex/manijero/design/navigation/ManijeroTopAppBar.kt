package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.ic_back
import manijero.shared.generated.resources.ic_info
import manijero.shared.generated.resources.ic_more
import manijero.shared.generated.resources.ic_search
import org.jetbrains.compose.resources.DrawableResource

/**
 * The top bar's search action. While [open] is false the bar shows a magnifier button (named
 * [label]) that calls [onOpen]; while true the bar becomes a close arrow (named [closeDescription])
 * plus the search field, and [onClose] ends the search. The caller owns [query] and decides what
 * closing does to it; the bar filters nothing.
 */
internal data class ManijeroTopBarSearch(
    val open: Boolean,
    val query: String,
    val label: String,
    val hint: String,
    val clearDescription: String,
    val closeDescription: String,
    val onOpen: () -> Unit,
    val onClose: () -> Unit,
    val onQueryChange: (String) -> Unit,
)

/** One entry of the top bar menu: its visible [label], an optional decorative [icon], the action. */
internal data class ManijeroTopBarMenuItem(
    val label: String,
    val icon: DrawableResource? = null,
    val onClick: () -> Unit,
)

/**
 * The flat brand bar: the 32 dp [ManijeroBrandMark] (identity, never a status), the caller's
 * [title], and an optional privacy-style action over a `surfaceContainerLowest` surface with a 1 dp
 * `outlineVariant` bottom divider and no shadow.
 *
 * From [WideWindowBreakpoint] the action is a `TextButton` with the visible [privacyLabel] and a
 * decorative `ic_info` glyph; below it the action is an `IconButton` whose accessible name is
 * [privacyDescription] (falling back to [privacyLabel]). Both keep Material's 48 dp target and
 * indication. The action is omitted when [onPrivacyClick] is null or when the caller supplies no
 * name at all, because an unnamed interactive control is not acceptable.
 *
 * When [onBack] and its accessible name [backDescription] are given, an up arrow (`ic_back` in a
 * 48 dp `IconButton`) leads the bar, like the back arrow of other phone apps. It is omitted without
 * a name, because an unnamed interactive control is not acceptable.
 *
 * With [screenTitle] the bar shows the screen's own [title] (marked as a heading) instead of the
 * brand mark and app name: this is the detail-screen form, after the up arrow.
 *
 * With [search], a magnifier button sits at the end of the bar (before the menu), always visible and
 * never inside the `⋮` menu; opening it turns the bar into the search field.
 *
 * When [menuItems] and the menu button's accessible name [menuDescription] are given, a `⋮`
 * button (`ic_more`, 48 dp) at the end of the bar opens a menu with one labelled row per item, each
 * with an optional decorative glyph. The menu is omitted without a name.
 *
 * The bar owns no window insets; the shell's `Scaffold` will own them.
 */
@Composable
internal fun ManijeroTopAppBar(
    title: String,
    modifier: Modifier = Modifier,
    onPrivacyClick: (() -> Unit)? = null,
    privacyLabel: String? = null,
    privacyDescription: String? = null,
    onBack: (() -> Unit)? = null,
    backDescription: String? = null,
    menuItems: List<ManijeroTopBarMenuItem> = emptyList(),
    menuDescription: String? = null,
    screenTitle: Boolean = false,
    search: ManijeroTopBarSearch? = null,
) {
    var menuOpen by remember { mutableStateOf(false) }
    val actionName = privacyDescription ?: privacyLabel
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.surfaceContainerLowest,
        contentColor = MaterialTheme.colorScheme.onSurface,
    ) {
        Column {
            BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
                val wide = maxWidth >= WideWindowBreakpoint
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = ManijeroLayout.MinTouchTarget)
                        .padding(
                            horizontal = screenHorizontalPadding(maxWidth),
                            vertical = ManijeroSpacing.Compact,
                        ),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
                ) {
                    if (onBack != null && backDescription != null) {
                        IconButton(
                            onClick = onBack,
                            modifier = Modifier.size(ManijeroLayout.MinTouchTarget),
                        ) {
                            ManijeroIcon(
                                resource = Res.drawable.ic_back,
                                contentDescription = backDescription,
                            )
                        }
                    }
                    if (search != null && search.open) {
                        // Search mode replaces the whole bar: close arrow, then the field.
                        val focus = remember { FocusRequester() }
                        LaunchedEffect(Unit) { focus.requestFocus() }
                        IconButton(
                            onClick = search.onClose,
                            modifier = Modifier.size(ManijeroLayout.MinTouchTarget),
                        ) {
                            ManijeroIcon(
                                resource = Res.drawable.ic_back,
                                contentDescription = search.closeDescription,
                            )
                        }
                        ManijeroSearchField(
                            value = search.query,
                            onValueChange = search.onQueryChange,
                            label = search.label,
                            clearDescription = search.clearDescription,
                            placeholder = search.hint,
                            modifier = Modifier.weight(1f).focusRequester(focus),
                        )
                        return@Row
                    }
                    // A top-level screen shows the brand mark and the app name; a detail screen shows
                    // its own title (as the screen's one heading) and no mark.
                    if (!screenTitle) ManijeroBrandMark()
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleLarge,
                        modifier = Modifier
                            .weight(1f)
                            .then(if (screenTitle) Modifier.semantics { heading() } else Modifier),
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (search != null) {
                        IconButton(
                            onClick = search.onOpen,
                            modifier = Modifier.size(ManijeroLayout.MinTouchTarget),
                        ) {
                            ManijeroIcon(
                                resource = Res.drawable.ic_search,
                                contentDescription = search.label,
                            )
                        }
                    }
                    if (menuItems.isNotEmpty() && menuDescription != null) {
                        Box {
                            IconButton(
                                onClick = { menuOpen = true },
                                modifier = Modifier.size(ManijeroLayout.MinTouchTarget),
                            ) {
                                ManijeroIcon(
                                    resource = Res.drawable.ic_more,
                                    contentDescription = menuDescription,
                                )
                            }
                            DropdownMenu(
                                expanded = menuOpen,
                                onDismissRequest = { menuOpen = false },
                            ) {
                                menuItems.forEach { item ->
                                    DropdownMenuItem(
                                        text = { Text(text = item.label) },
                                        leadingIcon = item.icon?.let { icon ->
                                            {
                                                ManijeroIcon(
                                                    resource = icon,
                                                    contentDescription = null,
                                                )
                                            }
                                        },
                                        onClick = {
                                            menuOpen = false
                                            item.onClick()
                                        },
                                        modifier = Modifier.heightIn(min = ManijeroLayout.MinTouchTarget),
                                    )
                                }
                            }
                        }
                    }
                    if (onPrivacyClick != null && actionName != null) {
                        if (wide && privacyLabel != null) {
                            TextButton(onClick = onPrivacyClick) {
                                ManijeroIcon(
                                    resource = Res.drawable.ic_info,
                                    contentDescription = null,
                                    size = ManijeroIconSize.Inline,
                                )
                                Spacer(modifier = Modifier.width(ManijeroSpacing.Compact))
                                Text(text = privacyLabel)
                            }
                        } else {
                            IconButton(onClick = onPrivacyClick) {
                                ManijeroIcon(
                                    resource = Res.drawable.ic_info,
                                    contentDescription = actionName,
                                )
                            }
                        }
                    }
                }
            }
            HorizontalDivider(
                thickness = ManijeroLayout.BorderWidth,
                color = MaterialTheme.colorScheme.outlineVariant,
            )
        }
    }
}

@Composable
private fun ManijeroTopAppBarPreviewFrame(dark: Boolean) {
    ManijeroTheme(darkTheme = dark) {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column {
                ManijeroTopAppBar(
                    title = "Manijero",
                    onPrivacyClick = {},
                    privacyLabel = "Privacidad",
                    privacyDescription = "Privacidad",
                )
                ManijeroTopAppBar(
                    title = "Manijero",
                    onPrivacyClick = {},
                    privacyDescription = "Privacidad",
                )
                ManijeroTopAppBar(title = "Manijero")
                ManijeroTopAppBar(title = "Manijero", onBack = {}, backDescription = "Volver")
                ManijeroTopAppBar(
                    title = "Terrenos eliminados",
                    onBack = {},
                    backDescription = "Volver",
                    screenTitle = true,
                )
                ManijeroTopAppBar(
                    title = "Manijero",
                    menuItems = listOf(ManijeroTopBarMenuItem("Opción", onClick = {})),
                    menuDescription = "Más opciones",
                )
            }
        }
    }
}

@Preview(name = "ManijeroTopAppBar — claro", widthDp = 900)
@Composable
private fun ManijeroTopAppBarLightPreview() = ManijeroTopAppBarPreviewFrame(dark = false)

@Preview(name = "ManijeroTopAppBar — oscuro", widthDp = 900)
@Composable
private fun ManijeroTopAppBarDarkPreview() = ManijeroTopAppBarPreviewFrame(dark = true)

@Preview(name = "ManijeroTopAppBar — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun ManijeroTopAppBarLargeTextPreview() = ManijeroTopAppBarPreviewFrame(dark = false)
