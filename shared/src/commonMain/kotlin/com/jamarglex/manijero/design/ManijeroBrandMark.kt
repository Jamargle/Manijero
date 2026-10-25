package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.brand_mark
import org.jetbrains.compose.resources.painterResource

/**
 * The Manijero identity mark: an open olive ring with a leaf, tinted `primary`.
 *
 * Identity, not status. The wrapper takes no content description, no colour, and no state, so a
 * caller cannot turn it into a check, seal, badge, or "verified" cue. It is decorative, draws at
 * exactly [size] without blur, and defaults to the prominent [ManijeroIconSize.Large] (32 dp);
 * 28 dp and 48 dp are valid call sites.
 */
@Composable
internal fun ManijeroBrandMark(
    modifier: Modifier = Modifier,
    size: Dp = ManijeroIconSize.Large,
) {
    Icon(
        painter = painterResource(Res.drawable.brand_mark),
        contentDescription = null,
        modifier = modifier.size(size),
        tint = MaterialTheme.colorScheme.primary,
    )
}

@Composable
private fun ManijeroBrandMarkPreviewRow() {
    Row(
        horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Medium),
        verticalAlignment = Alignment.Bottom,
    ) {
        listOf(28, 32, 48).forEach { sizeDp ->
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                ManijeroBrandMark(size = sizeDp.dp)
                Text(
                    text = "$sizeDp dp",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onBackground,
                )
            }
        }
    }
}

@Preview(name = "ManijeroBrandMark — claro", widthDp = 240)
@Composable
private fun ManijeroBrandMarkLightPreview() {
    ManijeroTheme(darkTheme = false) {
        Surface(
            color = MaterialTheme.colorScheme.background,
            modifier = Modifier.padding(ManijeroSpacing.Small),
        ) { ManijeroBrandMarkPreviewRow() }
    }
}

@Preview(name = "ManijeroBrandMark — oscuro", widthDp = 240)
@Composable
private fun ManijeroBrandMarkDarkPreview() {
    ManijeroTheme(darkTheme = true) {
        Surface(
            color = MaterialTheme.colorScheme.background,
            modifier = Modifier.padding(ManijeroSpacing.Small),
        ) { ManijeroBrandMarkPreviewRow() }
    }
}
