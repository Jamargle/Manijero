package com.jamarglex.manijero.design

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.olive_branch
import org.jetbrains.compose.resources.painterResource

/**
 * The decorative empty-state illustration: an olive sprig on a soft `primaryContainer` halo.
 *
 * The halo is painted here, in Compose, not in the vector, so the asset stays a monochrome mask and
 * both appearances share it. The wrapper takes no content description and no colour, adds no
 * semantics node, and scales between 160 dp and 200 dp (180 dp default) without clipping.
 */
@Composable
internal fun ManijeroOliveBranch(
    modifier: Modifier = Modifier,
    size: Dp = 180.dp,
) {
    Box(
        modifier = modifier
            .size(size)
            .background(color = MaterialTheme.colorScheme.primaryContainer, shape = CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painter = painterResource(Res.drawable.olive_branch),
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
            tint = MaterialTheme.colorScheme.onPrimaryContainer,
        )
    }
}

@Composable
private fun ManijeroOliveBranchPreviewRow() {
    Row(
        horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Medium),
        verticalAlignment = Alignment.Bottom,
    ) {
        listOf(160, 200).forEach { sizeDp ->
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                ManijeroOliveBranch(size = sizeDp.dp)
                Text(
                    text = "$sizeDp dp",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onBackground,
                )
            }
        }
    }
}

@Preview(name = "ManijeroOliveBranch — claro", widthDp = 440)
@Composable
private fun ManijeroOliveBranchLightPreview() {
    ManijeroTheme(darkTheme = false) {
        Box(
            modifier = Modifier
                .background(MaterialTheme.colorScheme.background)
                .padding(ManijeroSpacing.Small),
        ) { ManijeroOliveBranchPreviewRow() }
    }
}

@Preview(name = "ManijeroOliveBranch — oscuro", widthDp = 440)
@Composable
private fun ManijeroOliveBranchDarkPreview() {
    ManijeroTheme(darkTheme = true) {
        Box(
            modifier = Modifier
                .background(MaterialTheme.colorScheme.background)
                .padding(ManijeroSpacing.Small),
        ) { ManijeroOliveBranchPreviewRow() }
    }
}
