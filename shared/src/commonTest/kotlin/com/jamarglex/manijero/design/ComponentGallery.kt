package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.jamarglex.manijero.theme.ManijeroSpacing
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.ic_chat
import manijero.shared.generated.resources.ic_help
import manijero.shared.generated.resources.ic_lands

/**
 * Renders every component and tone in the layer, stacked, for human review only.
 *
 * It lives in `commonTest`, never in `commonMain`, because nothing in the app renders it: its only
 * consumers are the Desktop and Android host screenshot suites. Its Spanish labels are review
 * identifiers, not shipped copy, and the component layer owns no string resources. Rendering it is
 * not an accessibility, usability, device, or product claim.
 *
 * The gallery is parameterless on purpose: the narrow capture renders the same tree through a
 * 360 dp viewport at font scale 2, so there is no test-only configuration a shipped screen could
 * pick up. The top bar and the page layout are rendered for real: the bar spans the full window and
 * therefore shows its wide action from 840 dp and its compact action below it, while
 * [ManijeroScreen] lays out the scrolling content.
 */
@Composable
internal fun ComponentGallery() {
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
        contentColor = MaterialTheme.colorScheme.onBackground,
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            ManijeroTopAppBar(
                title = "Manijero",
                onPrivacyClick = {},
                privacyLabel = "Privacidad",
                privacyDescription = "Privacidad",
            )
            ManijeroScreen(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Galería de componentes",
                    style = MaterialTheme.typography.headlineSmall,
                )
                Text(
                    text = "Solo para revisión: no forma parte de ninguna pantalla.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                GalleryLabel(text = "SectionHeader")
                ManijeroSectionHeader(
                    title = "Encabezado con explicación",
                    description = "Texto de apoyo bajo el título.",
                    heading = true,
                )

                GalleryLabel(text = "Card")
                ManijeroCard { Text(text = "Surface: fondo elevado.") }
                ManijeroCard(tone = ManijeroCardTone.Tonal) {
                    Text(text = "Tonal: agrupa contenido.")
                }
                ManijeroCard(tone = ManijeroCardTone.Outlined) {
                    Text(text = "Outlined: borde de 1 dp.")
                }
                ManijeroCard(tone = ManijeroCardTone.Danger) {
                    Text(
                        text = "Danger: borde de error.",
                        color = MaterialTheme.colorScheme.error,
                    )
                }

                GalleryLabel(text = "Callout")
                ManijeroCallout(
                    text = "Info: respuesta orientativa.",
                    tone = ManijeroCalloutTone.Info,
                )
                ManijeroCallout(
                    text = "Caution: falta un dato opcional.",
                    tone = ManijeroCalloutTone.Caution,
                    title = "Aviso",
                )
                ManijeroCallout(
                    text = "Danger: no se pudo guardar.",
                    tone = ManijeroCalloutTone.Danger,
                    title = "Error",
                    action = {
                        TextButton(onClick = {}) { Text(text = "Reintentar") }
                    },
                )
                ManijeroCallout(
                    text = "Confirmation: guardado aquí.",
                    tone = ManijeroCalloutTone.Confirmation,
                    title = "Guardado",
                )

                GalleryLabel(text = "StatCard")
                ManijeroStatCard(
                    label = "Terrenos guardados",
                    value = "3",
                    supporting = "3 terrenos guardados.",
                )
                ManijeroStatCard(
                    label = "Superficie conocida",
                    value = "1,5 ha",
                    supporting = "1 de 3 terrenos con superficie.",
                )

                GalleryLabel(text = "EmptyState")
                ManijeroEmptyState(
                    title = "Todavía no hay terrenos",
                    body = "Añade un terreno para preguntar por él.",
                    action = { Button(onClick = {}) { Text(text = "Añadir terreno") } },
                )

                GalleryLabel(text = "AttributeChip")
                ManijeroAttributeChipRow()

                GalleryLabel(text = "ChoiceCard")
                ManijeroChoiceCard(
                    label = "No lo sé",
                    selected = true,
                    onSelect = {},
                    optionDescription = "Riego: No lo sé",
                )
                ManijeroChoiceCard(
                    label = "Secano",
                    selected = false,
                    onSelect = {},
                    optionDescription = "Riego: Secano",
                )
                ManijeroChoiceCard(
                    label = "Regadío",
                    selected = false,
                    onSelect = {},
                    optionDescription = "Riego: Regadío",
                    isError = true,
                )
                Text(
                    text = "Elige una opción para continuar.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )

                GalleryLabel(text = "Fields")
                ManijeroSearchField(
                    value = "olivar",
                    onValueChange = {},
                    label = "Buscar terreno",
                    clearDescription = "Borrar la búsqueda",
                )
                ManijeroDropdownField(
                    label = "Variedad",
                    options = listOf("Picual", "Hojiblanca", "Otra"),
                    selected = "Picual",
                    onSelect = {},
                )
                ManijeroDropdownField(
                    label = "Variedad",
                    options = listOf("Picual", "Hojiblanca", "Otra"),
                    selected = null,
                    onSelect = {},
                    placeholder = "Elige una variedad",
                    isError = true,
                    supportingText = "Elige una variedad para continuar.",
                )
                ManijeroMeasureField(
                    value = "",
                    onValueChange = {},
                    label = "Número de árboles",
                    errorText = "Escribe solo números.",
                )

                GalleryLabel(text = "BottomNavigation")
                ManijeroBottomNavigation(
                    destinations = galleryDestinations,
                    selectedIndex = 0,
                    onSelect = {},
                )

                GalleryLabel(text = "NavigationRail")
                ManijeroNavigationRail(
                    destinations = galleryDestinations,
                    selectedIndex = 1,
                    onSelect = {},
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ManijeroAttributeChipRow() {
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

private val galleryDestinations = listOf(
    ManijeroDestination(label = "Asistente", icon = Res.drawable.ic_chat),
    ManijeroDestination(label = "Mis terrenos", icon = Res.drawable.ic_lands),
    ManijeroDestination(label = "Ayuda", icon = Res.drawable.ic_help),
)

@Composable
private fun GalleryLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}
