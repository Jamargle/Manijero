package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.ManijeroShapes
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme

/**
 * The shared empty state: the decorative [ManijeroOliveBranch], a real heading, a plain explanation,
 * and exactly one [action] slot.
 *
 * The illustration carries no semantics node, so a screen reader hears the heading and the body;
 * the caller supplies the single button (or other control) and its Spanish label, and the component
 * adds none of its own.
 */
@Composable
internal fun ManijeroEmptyState(
    title: String,
    body: String,
    action: @Composable () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = ManijeroShapes.ExtraLarge,
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        contentColor = MaterialTheme.colorScheme.onSurface,
    ) {
        Column(
            modifier = Modifier.padding(ManijeroSpacing.Medium),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Comfortable),
        ) {
            ManijeroOliveBranch()
            Text(
                text = title,
                style = MaterialTheme.typography.headlineSmall,
                textAlign = TextAlign.Center,
                modifier = Modifier.semantics { heading() },
            )
            Text(
                text = body,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            action()
        }
    }
}

@Composable
private fun ManijeroEmptyStatePreviewContent() {
    ManijeroEmptyState(
        title = "Todavía no hay terrenos",
        body = "Añade un terreno con su nombre para poder preguntar por él.",
        action = { Button(onClick = {}) { Text(text = "Añadir terreno") } },
    )
}

@Composable
private fun ManijeroEmptyStatePreviewFrame(dark: Boolean) {
    ManijeroTheme(darkTheme = dark) {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ManijeroSpacing.Small),
            ) { ManijeroEmptyStatePreviewContent() }
        }
    }
}

@Preview(name = "ManijeroEmptyState — claro", widthDp = 380, heightDp = 560)
@Composable
private fun ManijeroEmptyStateLightPreview() = ManijeroEmptyStatePreviewFrame(dark = false)

@Preview(name = "ManijeroEmptyState — oscuro", widthDp = 380, heightDp = 560)
@Composable
private fun ManijeroEmptyStateDarkPreview() = ManijeroEmptyStatePreviewFrame(dark = true)

@Preview(name = "ManijeroEmptyState — texto grande", widthDp = 360, heightDp = 720, fontScale = 2f)
@Composable
private fun ManijeroEmptyStateLargeTextPreview() = ManijeroEmptyStatePreviewFrame(dark = false)
