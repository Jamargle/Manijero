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
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme

/**
 * A section title with an optional plain-Spanish explanation.
 *
 * The title is announced as a heading only when the caller passes `heading = true`; a decorative
 * label or a repeated caption must not create a fake heading in the screen-reader outline.
 */
@Composable
internal fun ManijeroSectionHeader(
    title: String,
    modifier: Modifier = Modifier,
    description: String? = null,
    heading: Boolean = false,
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = if (heading) Modifier.semantics { heading() } else Modifier,
        )
        if (description != null) {
            Text(
                text = description,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ManijeroSectionHeaderPreviewContent() {
    ManijeroSectionHeader(
        title = "Datos de la parcela",
        description = "Se muestran solo los datos que has guardado.",
        heading = true,
    )
    ManijeroSectionHeader(title = "Sin explicación")
}

@Composable
private fun ManijeroSectionHeaderPreviewFrame(dark: Boolean) {
    ManijeroTheme(darkTheme = dark) {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ManijeroSpacing.Medium),
                verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Medium),
            ) { ManijeroSectionHeaderPreviewContent() }
        }
    }
}

@Preview(name = "ManijeroSectionHeader — claro", widthDp = 380)
@Composable
private fun ManijeroSectionHeaderLightPreview() = ManijeroSectionHeaderPreviewFrame(dark = false)

@Preview(name = "ManijeroSectionHeader — oscuro", widthDp = 380)
@Composable
private fun ManijeroSectionHeaderDarkPreview() = ManijeroSectionHeaderPreviewFrame(dark = true)

@Preview(name = "ManijeroSectionHeader — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun ManijeroSectionHeaderLargeTextPreview() =
    ManijeroSectionHeaderPreviewFrame(dark = false)
