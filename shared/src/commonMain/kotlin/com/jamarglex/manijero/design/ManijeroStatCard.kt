package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme

/**
 * A summary metric: a label, the caller's already-formatted value, and a required [supporting]
 * caption that states what the value counts or how many records contributed.
 *
 * [supporting] has no default on purpose. The component never formats, totals, rounds, or invents a
 * value, so a card cannot render a bare number without saying what it is and how complete it is.
 */
@Composable
internal fun ManijeroStatCard(
    label: String,
    value: String,
    supporting: String,
    modifier: Modifier = Modifier,
) {
    ManijeroCard(modifier = modifier, tone = ManijeroCardTone.Outlined) {
        Text(
            text = label,
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = value, style = MaterialTheme.typography.headlineMedium)
        Text(
            text = supporting,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun ManijeroStatCardPreviewContent() {
    ManijeroStatCard(
        label = "Terrenos guardados",
        value = "3",
        supporting = "3 terrenos en este dispositivo.",
    )
    ManijeroStatCard(
        label = "Superficie conocida",
        value = "1,5 ha",
        supporting = "1 de 3 terrenos tiene superficie; el resto sigue sin dato.",
    )
}

@Composable
private fun ManijeroStatCardPreviewFrame(dark: Boolean) {
    ManijeroTheme(darkTheme = dark) {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ManijeroSpacing.Small),
                verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
            ) { ManijeroStatCardPreviewContent() }
        }
    }
}

@Preview(name = "ManijeroStatCard — claro", widthDp = 380)
@Composable
private fun ManijeroStatCardLightPreview() = ManijeroStatCardPreviewFrame(dark = false)

@Preview(name = "ManijeroStatCard — oscuro", widthDp = 380)
@Composable
private fun ManijeroStatCardDarkPreview() = ManijeroStatCardPreviewFrame(dark = true)

@Preview(name = "ManijeroStatCard — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun ManijeroStatCardLargeTextPreview() = ManijeroStatCardPreviewFrame(dark = false)
