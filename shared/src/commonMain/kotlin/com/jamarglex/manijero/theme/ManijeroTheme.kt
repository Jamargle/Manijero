package com.jamarglex.manijero.theme

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.add_land_save_failed
import org.jetbrains.compose.resources.stringResource

/**
 * The single shared theme: [ManijeroLightColorScheme] roles, [ManijeroTypography], and the
 * [LocalManijeroSemanticColors] values Material 3 cannot express.
 *
 * Apply it **once**, inside [com.jamarglex.manijero.App], so Android, Desktop, the iOS scaffold, and
 * every preview inherit one palette. Platform entry points must not wrap it again.
 *
 * Light-only by decision: no dark tokens exist, and `DESIGN.md` defines one warm palette for the MVP.
 * The theme deliberately does not call `isSystemInDarkTheme()`, so a person whose system is in dark
 * mode still sees the light warm theme instead of an unverified dark palette.
 *
 * Shapes stay at the Material 3 baseline, which already provides the simple rounded cards and
 * buttons `DESIGN.md` asks for.
 */
@Composable
internal fun ManijeroTheme(content: @Composable () -> Unit) {
    CompositionLocalProvider(
        LocalManijeroSemanticColors provides ManijeroLightSemanticColors,
    ) {
        MaterialTheme(
            colorScheme = ManijeroLightColorScheme,
            typography = ManijeroTypography,
            content = content,
        )
    }
}

private data class TokenSwatch(
    val name: String,
    val hex: String,
    val color: Color,
)

/**
 * Review-only board so caution and danger can be inspected before `response_states` ships. It is not
 * part of any screen, and its labels are preview samples (the danger line reuses an existing shipped
 * string), so no new shipped copy is introduced.
 */
@Composable
private fun ManijeroTokenBoard() {
    val tokens = listOf(
        TokenSwatch("olive-800", "#354B32", ManijeroOlive800),
        TokenSwatch("olive-900", "#263724", ManijeroOlive900),
        TokenSwatch("canvas", "#F7F6F0", ManijeroCanvas),
        TokenSwatch("surface", "#FFFFFF", ManijeroSurface),
        TokenSwatch("text-primary", "#1D221B", ManijeroTextPrimary),
        TokenSwatch("text-secondary", "#4B5149", ManijeroTextSecondary),
        TokenSwatch("border", "#777D73", ManijeroBorder),
        TokenSwatch("caution", "#704600", ManijeroCaution),
        TokenSwatch("caution-surface", "#FFF2D4", ManijeroCautionSurface),
        TokenSwatch("danger", "#A12622", ManijeroDanger),
    )
    val semanticColors = LocalManijeroSemanticColors.current

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                text = "Tokens de Manijero",
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Text(
                text = "Solo para revisión del tema compartido.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            tokens.forEach { token ->
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .size(40.dp)
                            .background(token.color)
                            .border(1.dp, MaterialTheme.colorScheme.outline),
                    )
                    Text(
                        text = "${token.name}  ${token.hex}",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onBackground,
                    )
                }
            }

            Surface(
                shape = RoundedCornerShape(12.dp),
                color = semanticColors.cautionSurface,
                border = BorderStroke(1.dp, semanticColors.caution),
            ) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        text = "Aviso",
                        style = MaterialTheme.typography.labelLarge,
                        color = semanticColors.caution,
                    )
                    Text(
                        text = "Revisa este dato antes de continuar.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = semanticColors.caution,
                    )
                }
            }

            Text(
                text = stringResource(Res.string.add_land_save_failed),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.error,
            )

            Text(
                text = "Selección",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = true, onClick = null)
                Text(
                    text = "Seleccionado",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.padding(start = 12.dp),
                )
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = false, onClick = null)
                Text(
                    text = "No seleccionado",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.padding(start = 12.dp),
                )
            }
        }
    }
}

@Preview(name = "Manijero tokens — board", widthDp = 420)
@Composable
private fun ManijeroTokenBoardPreview() {
    ManijeroTheme { ManijeroTokenBoard() }
}

@Preview(name = "Manijero tokens — large text", widthDp = 420, fontScale = 2f)
@Composable
private fun ManijeroTokenBoardLargeTextPreview() {
    ManijeroTheme { ManijeroTokenBoard() }
}
