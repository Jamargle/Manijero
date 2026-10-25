package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.ic_info

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
 * The bar owns no window insets; the shell's `Scaffold` will own them.
 */
@Composable
internal fun ManijeroTopAppBar(
    title: String,
    modifier: Modifier = Modifier,
    onPrivacyClick: (() -> Unit)? = null,
    privacyLabel: String? = null,
    privacyDescription: String? = null,
) {
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
                    ManijeroBrandMark()
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleLarge,
                        modifier = Modifier.weight(1f),
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
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
