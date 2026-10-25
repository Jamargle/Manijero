package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.ic_add
import manijero.shared.generated.resources.ic_clear
import manijero.shared.generated.resources.ic_search
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.painterResource

/**
 * Draws one shared UI glyph at exactly [size], tinted from the current content colour.
 *
 * Every vector in the set is a single black mask, so the colour it renders in comes only from the
 * wrapper: [tint] defaults to `LocalContentColor`, which follows the surrounding surface/theme.
 * [contentDescription] deliberately has no default, so a caller has to decide whether the glyph
 * carries meaning (`null` means decorative) instead of inheriting one silently.
 *
 * The wrapper owns no padding, touch target, or click behaviour. An interactive icon belongs inside
 * the consuming feature's `IconButton`, which supplies `ManijeroLayout.MinTouchTarget`.
 */
@Composable
internal fun ManijeroIcon(
    resource: DrawableResource,
    contentDescription: String?,
    modifier: Modifier = Modifier,
    size: Dp = ManijeroIconSize.Default,
    tint: Color = LocalContentColor.current,
) {
    Icon(
        painter = painterResource(resource),
        contentDescription = contentDescription,
        modifier = modifier.size(size),
        tint = tint,
    )
}

/** Legend-free review row: the same glyph at the default 24 dp and the inline 20 dp. */
@Composable
private fun ManijeroIconPreviewRow() {
    Row(
        horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Medium),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            ManijeroIcon(resource = Res.drawable.ic_search, contentDescription = null)
            Text(text = "24 dp", style = MaterialTheme.typography.labelSmall)
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            ManijeroIcon(
                resource = Res.drawable.ic_search,
                contentDescription = null,
                size = ManijeroIconSize.Inline,
            )
            Text(text = "20 dp", style = MaterialTheme.typography.labelSmall)
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            ManijeroIcon(resource = Res.drawable.ic_add, contentDescription = null)
            Text(text = "24 dp", style = MaterialTheme.typography.labelSmall)
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            ManijeroIcon(resource = Res.drawable.ic_clear, contentDescription = null)
            Text(text = "24 dp", style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Preview(name = "ManijeroIcon — claro", widthDp = 260)
@Composable
private fun ManijeroIconLightPreview() {
    ManijeroTheme(darkTheme = false) {
        Surface(
            color = MaterialTheme.colorScheme.background,
            contentColor = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.padding(ManijeroSpacing.Small),
        ) { ManijeroIconPreviewRow() }
    }
}

@Preview(name = "ManijeroIcon — oscuro", widthDp = 260)
@Composable
private fun ManijeroIconDarkPreview() {
    ManijeroTheme(darkTheme = true) {
        Surface(
            color = MaterialTheme.colorScheme.background,
            contentColor = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.padding(ManijeroSpacing.Small),
        ) { ManijeroIconPreviewRow() }
    }
}
