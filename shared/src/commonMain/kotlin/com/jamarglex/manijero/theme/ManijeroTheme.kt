package com.jamarglex.manijero.theme

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
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
import kotlin.math.roundToInt
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.add_land_save_failed
import org.jetbrains.compose.resources.stringResource

/**
 * The single shared theme: the paired light/dark Manijero color schemes, the shared shape scale, and
 * the [LocalManijeroSemanticColors] values Material 3 cannot express.
 *
 * Apply it **once**, inside [com.jamarglex.manijero.App], so Android, Desktop, the iOS scaffold, and
 * every preview inherit one palette. Platform entry points must not wrap it again.
 *
 * The system appearance selects the matching shared light or dark palette. The [darkTheme] parameter
 * defaults to [isSystemInDarkTheme] and can be set explicitly by previews and tests.
 *
 * Typography stays at the Material 3 default, which resolves to the platform font, so no type
 * family, size, weight, or font asset is owned here.
 */
@Composable
internal fun ManijeroTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val scheme = selectManijeroColorScheme(darkTheme)
    CompositionLocalProvider(
        LocalManijeroSemanticColors provides if (darkTheme) ManijeroDarkSemanticColors else ManijeroLightSemanticColors,
    ) {
        MaterialTheme(
            colorScheme = scheme,
            shapes = ManijeroShapes.Material,
            content = content,
        )
    }
}

/** Pure appearance mapping shared by the theme and common unit tests. */
internal fun selectManijeroColorScheme(darkTheme: Boolean) =
    if (darkTheme) ManijeroDarkColorScheme else ManijeroLightColorScheme

private data class TokenSwatch(
    val name: String,
    val color: Color,
)

/** Formats the colour the theme actually uses, so the board cannot drift from a typed label. */
private fun Color.hexLabel(): String {
    fun channel(value: Float): String =
        (value * 255f).roundToInt().toString(16).uppercase().padStart(2, '0')

    return "#${channel(red)}${channel(green)}${channel(blue)}"
}

/**
 * Review-only board for the shared palette: every documented role, the semantic colours, and the
 * four land-attribute chips, each labelled with the colour it renders. It is not part of any screen
 * and its labels are preview samples (the danger line reuses an existing shipped string), so no new
 * shipped copy is introduced.
 */
@Composable
private fun ManijeroTokenBoard() {
    val scheme = MaterialTheme.colorScheme
    val semantic = LocalManijeroSemanticColors.current
    val roles = listOf(
        TokenSwatch("primary", scheme.primary),
        TokenSwatch("onPrimary", scheme.onPrimary),
        TokenSwatch("primaryContainer", scheme.primaryContainer),
        TokenSwatch("onPrimaryContainer", scheme.onPrimaryContainer),
        TokenSwatch("inversePrimary", scheme.inversePrimary),
        TokenSwatch("secondary", scheme.secondary),
        TokenSwatch("onSecondary", scheme.onSecondary),
        TokenSwatch("secondaryContainer", scheme.secondaryContainer),
        TokenSwatch("onSecondaryContainer", scheme.onSecondaryContainer),
        TokenSwatch("tertiary", scheme.tertiary),
        TokenSwatch("onTertiary", scheme.onTertiary),
        TokenSwatch("tertiaryContainer", scheme.tertiaryContainer),
        TokenSwatch("onTertiaryContainer", scheme.onTertiaryContainer),
        TokenSwatch("background", scheme.background),
        TokenSwatch("onBackground", scheme.onBackground),
        TokenSwatch("surface", scheme.surface),
        TokenSwatch("onSurface", scheme.onSurface),
        TokenSwatch("surfaceVariant", scheme.surfaceVariant),
        TokenSwatch("onSurfaceVariant", scheme.onSurfaceVariant),
        TokenSwatch("surfaceTint", scheme.surfaceTint),
        TokenSwatch("inverseSurface", scheme.inverseSurface),
        TokenSwatch("inverseOnSurface", scheme.inverseOnSurface),
        TokenSwatch("error", scheme.error),
        TokenSwatch("onError", scheme.onError),
        TokenSwatch("errorContainer", scheme.errorContainer),
        TokenSwatch("onErrorContainer", scheme.onErrorContainer),
        TokenSwatch("outline", scheme.outline),
        TokenSwatch("outlineVariant", scheme.outlineVariant),
        TokenSwatch("scrim", scheme.scrim),
        TokenSwatch("surfaceBright", scheme.surfaceBright),
        TokenSwatch("surfaceDim", scheme.surfaceDim),
        TokenSwatch("surfaceContainerLowest", scheme.surfaceContainerLowest),
        TokenSwatch("surfaceContainerLow", scheme.surfaceContainerLow),
        TokenSwatch("surfaceContainer", scheme.surfaceContainer),
        TokenSwatch("surfaceContainerHigh", scheme.surfaceContainerHigh),
        TokenSwatch("surfaceContainerHighest", scheme.surfaceContainerHighest),
    )
    val chips = listOf(
        TokenSwatch("Secano", scheme.secondaryContainer) to scheme.onSecondaryContainer,
        TokenSwatch("Regadío", scheme.primaryContainer) to scheme.onPrimaryContainer,
        TokenSwatch("Ecológico", semantic.ecoContainer) to semantic.onEcoContainer,
        TokenSwatch("No lo sé", scheme.surfaceContainerHighest) to scheme.onSurface,
    )

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(ManijeroSpacing.Medium),
            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Comfortable),
        ) {
            Text(
                text = "Paleta de Manijero",
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Text(
                text = "Solo para revisión del tema compartido.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            SectionTitle("Roles de color")
            roles.forEach { token -> SwatchRow(token) }

            SectionTitle("Colores semánticos")
            SwatchRow(TokenSwatch("caution", semantic.caution))
            SwatchRow(TokenSwatch("cautionSurface", semantic.cautionSurface))
            SwatchRow(TokenSwatch("onCaution", semantic.onCaution))
            SwatchRow(TokenSwatch("primaryStrong", semantic.primaryStrong))
            SwatchRow(TokenSwatch("ecoContainer", semantic.ecoContainer))
            SwatchRow(TokenSwatch("onEcoContainer", semantic.onEcoContainer))

            Surface(
                shape = ManijeroShapes.Medium,
                color = semantic.cautionSurface,
                border = BorderStroke(1.dp, semantic.caution),
            ) {
                Column(
                    modifier = Modifier.padding(ManijeroSpacing.Small),
                    verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
                ) {
                    Text(
                        text = "Aviso",
                        style = MaterialTheme.typography.labelLarge,
                        color = semantic.caution,
                    )
                    Text(
                        text = "Revisa este dato antes de continuar.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = semantic.caution,
                    )
                }
            }

            Surface(
                shape = ManijeroShapes.Medium,
                color = semantic.caution,
            ) {
                Text(
                    text = "onCaution sobre caution",
                    modifier = Modifier.padding(ManijeroSpacing.Small),
                    style = MaterialTheme.typography.labelLarge,
                    color = semantic.onCaution,
                )
            }

            SectionTitle("Chips de terreno")
            chips.forEach { (chip, ink) -> ChipRow(chip, ink) }

            SectionTitle("Estados")
            Text(
                text = stringResource(Res.string.add_land_save_failed),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.error,
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = true, onClick = null)
                Text(
                    text = "Seleccionado",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.padding(start = ManijeroSpacing.Small),
                )
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = false, onClick = null)
                Text(
                    text = "No seleccionado",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.padding(start = ManijeroSpacing.Small),
                )
            }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.onBackground,
    )
}

@Composable
private fun SwatchRow(token: TokenSwatch) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
    ) {
        Box(
            modifier = Modifier
                .size(40.dp)
                .background(token.color)
                .border(ManijeroLayout.BorderWidth, MaterialTheme.colorScheme.outline),
        )
        Text(
            text = "${token.name}  ${token.color.hexLabel()}",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onBackground,
        )
    }
}

/** A chip always shows its own text, so the pair can be judged without relying on colour alone. */
@Composable
private fun ChipRow(chip: TokenSwatch, ink: Color) {
    Surface(
        shape = ManijeroShapes.Medium,
        color = chip.color,
        border = BorderStroke(ManijeroLayout.BorderWidth, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Text(
            text = "${chip.name}  ${chip.color.hexLabel()} / ${ink.hexLabel()}",
            modifier = Modifier.padding(
                horizontal = ManijeroSpacing.Small,
                vertical = ManijeroSpacing.Micro,
            ),
            style = MaterialTheme.typography.labelLarge,
            color = ink,
        )
    }
}

@Preview(name = "Manijero tokens — board", widthDp = 420)
@Composable
private fun ManijeroTokenBoardPreview() {
    ManijeroTheme(darkTheme = false) { ManijeroTokenBoard() }
}

@Preview(name = "Manijero tokens — dark", widthDp = 420)
@Composable
private fun ManijeroTokenBoardDarkPreview() {
    ManijeroTheme(darkTheme = true) { ManijeroTokenBoard() }
}

@Preview(name = "Manijero tokens — large text", widthDp = 420, fontScale = 2f)
@Composable
private fun ManijeroTokenBoardLargeTextPreview() {
    ManijeroTheme(darkTheme = false) { ManijeroTokenBoard() }
}
