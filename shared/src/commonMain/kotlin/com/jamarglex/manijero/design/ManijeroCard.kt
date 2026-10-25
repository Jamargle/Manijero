package com.jamarglex.manijero.design

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroShapes
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme

/**
 * The four accepted card tones.
 *
 * [Surface] and [Outlined] paint the raised surface colour; `Tonal` uses the low container for a
 * grouped block; `Danger` uses the raised surface with an error boundary, so danger is always
 * carried by text as well as the border.
 */
internal enum class ManijeroCardTone {
    Surface,
    Tonal,
    Outlined,
    Danger,
}

/**
 * The shared card container: 16 dp large radius, comfortable internal padding, and a 1 dp border
 * where the tone defines one ([ManijeroCardTone.Outlined] uses `outlineVariant`,
 * [ManijeroCardTone.Danger] uses `error`).
 *
 * The card itself is not clickable and adds no semantics of its own: a caller that needs an action
 * puts an interactive child (a button, a choice row, a link) inside it.
 */
@Composable
internal fun ManijeroCard(
    modifier: Modifier = Modifier,
    tone: ManijeroCardTone = ManijeroCardTone.Outlined,
    content: @Composable ColumnScope.() -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val container = when (tone) {
        ManijeroCardTone.Surface,
        ManijeroCardTone.Outlined,
        ManijeroCardTone.Danger,
        -> scheme.surfaceContainerLowest

        ManijeroCardTone.Tonal -> scheme.surfaceContainerLow
    }
    val border = when (tone) {
        ManijeroCardTone.Surface,
        ManijeroCardTone.Tonal,
        -> null

        ManijeroCardTone.Outlined -> BorderStroke(ManijeroLayout.BorderWidth, scheme.outlineVariant)
        ManijeroCardTone.Danger -> BorderStroke(ManijeroLayout.BorderWidth, scheme.error)
    }

    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = ManijeroShapes.Large,
        color = container,
        contentColor = scheme.onSurface,
        border = border,
    ) {
        Column(
            modifier = Modifier.padding(ManijeroSpacing.Comfortable),
            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact),
            content = content,
        )
    }
}

@Composable
private fun ManijeroCardPreviewColumn() {
    ManijeroCard { Text(text = "Surface: el fondo elevado de una tarjeta.") }
    ManijeroCard(tone = ManijeroCardTone.Tonal) { Text(text = "Tonal: agrupa contenido relacionado.") }
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        Text(text = "Outlined: borde suave de 1 dp.")
    }
    ManijeroCard(tone = ManijeroCardTone.Danger) {
        Text(
            text = "Danger: borde de error, siempre con texto.",
            color = MaterialTheme.colorScheme.error,
        )
    }
}

@Composable
private fun ManijeroCardPreviewFrame(darkTheme: Boolean) {
    ManijeroTheme(darkTheme = darkTheme) {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ManijeroSpacing.Small),
                verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
            ) { ManijeroCardPreviewColumn() }
        }
    }
}

@Preview(name = "ManijeroCard — claro", widthDp = 380)
@Composable
private fun ManijeroCardLightPreview() = ManijeroCardPreviewFrame(darkTheme = false)

@Preview(name = "ManijeroCard — oscuro", widthDp = 380)
@Composable
private fun ManijeroCardDarkPreview() = ManijeroCardPreviewFrame(darkTheme = true)

@Preview(name = "ManijeroCard — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun ManijeroCardLargeTextPreview() = ManijeroCardPreviewFrame(darkTheme = false)

