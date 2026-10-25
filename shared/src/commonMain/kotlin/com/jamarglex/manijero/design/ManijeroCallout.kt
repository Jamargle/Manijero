package com.jamarglex.manijero.design

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.LocalManijeroSemanticColors
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroShapes
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.ic_check
import manijero.shared.generated.resources.ic_info
import manijero.shared.generated.resources.ic_warning
import org.jetbrains.compose.resources.DrawableResource

/** The four accepted callout tones, each with its icon and its accepted token pair. */
internal enum class ManijeroCalloutTone {
    Info,
    Caution,
    Danger,
    Confirmation,
}

private data class CalloutPalette(
    val container: Color,
    val ink: Color,
    val border: Color,
    val icon: DrawableResource,
)

@Composable
private fun calloutPalette(tone: ManijeroCalloutTone): CalloutPalette {
    val scheme = MaterialTheme.colorScheme
    val semantic = LocalManijeroSemanticColors.current
    return when (tone) {
        ManijeroCalloutTone.Info -> CalloutPalette(
            container = scheme.surfaceContainerLow,
            ink = scheme.onSurface,
            border = scheme.outlineVariant,
            icon = Res.drawable.ic_info,
        )

        ManijeroCalloutTone.Caution -> CalloutPalette(
            container = semantic.cautionSurface,
            ink = semantic.caution,
            border = semantic.caution,
            icon = Res.drawable.ic_warning,
        )

        ManijeroCalloutTone.Danger -> CalloutPalette(
            container = scheme.errorContainer,
            ink = scheme.error,
            border = scheme.error,
            icon = Res.drawable.ic_warning,
        )

        ManijeroCalloutTone.Confirmation -> CalloutPalette(
            container = scheme.primaryContainer,
            ink = scheme.onPrimaryContainer,
            border = scheme.primary,
            icon = Res.drawable.ic_check,
        )
    }
}

/**
 * An inline message block: always an icon plus the caller's text, never colour alone.
 *
 * Each tone uses its accepted pair (`surfaceContainerLow`/`onSurface`, `cautionSurface`/`caution`,
 * `errorContainer`/`error`, `primaryContainer`/`onPrimaryContainer`) and a same-hue 1 dp boundary.
 * Only the title-and-text block is marked as a polite live region, so a message that appears after
 * an action is announced once; [action] stays its own focusable node and the component adds no
 * control of its own.
 */
@Composable
internal fun ManijeroCallout(
    text: String,
    tone: ManijeroCalloutTone,
    modifier: Modifier = Modifier,
    title: String? = null,
    action: (@Composable () -> Unit)? = null,
) {
    val palette = calloutPalette(tone)
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = ManijeroShapes.Large,
        color = palette.container,
        contentColor = palette.ink,
        border = BorderStroke(ManijeroLayout.BorderWidth, palette.border),
    ) {
        Row(
            modifier = Modifier.padding(ManijeroSpacing.Comfortable),
            horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
            verticalAlignment = Alignment.Top,
        ) {
            ManijeroIcon(
                resource = palette.icon,
                contentDescription = null,
                size = ManijeroIconSize.Inline,
                tint = palette.ink,
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
            ) {
                Column(
                    modifier = Modifier.semantics(mergeDescendants = true) {
                        liveRegion = LiveRegionMode.Polite
                    },
                    verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
                ) {
                    if (title != null) {
                        Text(text = title, style = MaterialTheme.typography.titleMedium)
                    }
                    Text(text = text, style = MaterialTheme.typography.bodyLarge)
                }
                if (action != null) {
                    Spacer(modifier = Modifier.height(ManijeroSpacing.Compact))
                    action()
                }
            }
        }
    }
}

@Composable
private fun ManijeroCalloutPreviewContent() {
    ManijeroCallout(text = "Respuesta orientativa, no oficial.", tone = ManijeroCalloutTone.Info)
    ManijeroCallout(
        text = "Falta la fecha de la parcela. Puedes seguir sin ella.",
        tone = ManijeroCalloutTone.Caution,
        title = "Revisa este dato",
    )
    ManijeroCallout(
        text = "No se ha podido guardar. Inténtalo de nuevo.",
        tone = ManijeroCalloutTone.Danger,
        title = "Algo ha fallado",
        action = { TextButton(onClick = {}) { Text(text = "Reintentar") } },
    )
    ManijeroCallout(
        text = "El terreno se ha guardado solo en este dispositivo.",
        tone = ManijeroCalloutTone.Confirmation,
        title = "Guardado",
    )
}

@Composable
private fun ManijeroCalloutPreviewFrame(dark: Boolean) {
    ManijeroTheme(darkTheme = dark) {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ManijeroSpacing.Small),
                verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
            ) { ManijeroCalloutPreviewContent() }
        }
    }
}

@Preview(name = "ManijeroCallout — claro", widthDp = 380)
@Composable
private fun ManijeroCalloutLightPreview() = ManijeroCalloutPreviewFrame(dark = false)

@Preview(name = "ManijeroCallout — oscuro", widthDp = 380)
@Composable
private fun ManijeroCalloutDarkPreview() = ManijeroCalloutPreviewFrame(dark = true)

@Preview(name = "ManijeroCallout — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun ManijeroCalloutLargeTextPreview() = ManijeroCalloutPreviewFrame(dark = false)
