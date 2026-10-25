package com.jamarglex.manijero.design

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.LocalManijeroSemanticColors
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroShapes
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme

/** The four accepted land-attribute chip tones. */
internal enum class ManijeroChipTone {
    Dryland,
    Irrigated,
    Organic,
    Neutral,
}

/**
 * A non-interactive land-attribute chip. It always carries its own [label]: the tone's accepted
 * pair (`secondaryContainer`, `primaryContainer`, the semantic eco pair, or
 * `surfaceContainerHighest`) is decoration, never the only cue for a status, and the chip owns no
 * click, target, or state.
 */
@Composable
internal fun ManijeroAttributeChip(
    label: String,
    tone: ManijeroChipTone,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val semantic = LocalManijeroSemanticColors.current
    val container: Color
    val ink: Color
    when (tone) {
        ManijeroChipTone.Dryland -> {
            container = scheme.secondaryContainer
            ink = scheme.onSecondaryContainer
        }

        ManijeroChipTone.Irrigated -> {
            container = scheme.primaryContainer
            ink = scheme.onPrimaryContainer
        }

        ManijeroChipTone.Organic -> {
            container = semantic.ecoContainer
            ink = semantic.onEcoContainer
        }

        ManijeroChipTone.Neutral -> {
            container = scheme.surfaceContainerHighest
            ink = scheme.onSurface
        }
    }

    Surface(
        modifier = modifier,
        shape = ManijeroShapes.Medium,
        color = container,
        contentColor = ink,
        border = BorderStroke(ManijeroLayout.BorderWidth, scheme.outlineVariant),
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelLarge,
            modifier = Modifier.padding(
                horizontal = ManijeroSpacing.Small,
                vertical = ManijeroSpacing.Micro,
            ),
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ManijeroAttributeChipPreviewContent() {
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact),
        verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact),
    ) {
        ManijeroAttributeChip(label = "Secano", tone = ManijeroChipTone.Dryland)
        ManijeroAttributeChip(label = "Regadío", tone = ManijeroChipTone.Irrigated)
        ManijeroAttributeChip(label = "Ecológico", tone = ManijeroChipTone.Organic)
        ManijeroAttributeChip(label = "No lo sé", tone = ManijeroChipTone.Neutral)
    }
}

@Composable
private fun ManijeroAttributeChipPreviewFrame(dark: Boolean) {
    ManijeroTheme(darkTheme = dark) {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ManijeroSpacing.Small),
            ) { ManijeroAttributeChipPreviewContent() }
        }
    }
}

@Preview(name = "ManijeroAttributeChip — claro", widthDp = 380)
@Composable
private fun ManijeroAttributeChipLightPreview() = ManijeroAttributeChipPreviewFrame(dark = false)

@Preview(name = "ManijeroAttributeChip — oscuro", widthDp = 380)
@Composable
private fun ManijeroAttributeChipDarkPreview() = ManijeroAttributeChipPreviewFrame(dark = true)

@Preview(name = "ManijeroAttributeChip — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun ManijeroAttributeChipLargeTextPreview() =
    ManijeroAttributeChipPreviewFrame(dark = false)
