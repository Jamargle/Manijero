package com.jamarglex.manijero.lands

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.add_land_production_conventional
import manijero.shared.generated.resources.add_land_production_mixed
import manijero.shared.generated.resources.add_land_production_organic
import manijero.shared.generated.resources.add_land_saved
import manijero.shared.generated.resources.add_land_unknown
import manijero.shared.generated.resources.add_land_water_dryland
import manijero.shared.generated.resources.add_land_water_irrigated
import manijero.shared.generated.resources.add_land_water_mixed
import manijero.shared.generated.resources.chat_home_lands
import manijero.shared.generated.resources.edit_land_saved
import manijero.shared.generated.resources.land_list_add
import manijero.shared.generated.resources.land_list_back
import manijero.shared.generated.resources.land_list_description
import manijero.shared.generated.resources.land_list_edit
import manijero.shared.generated.resources.land_list_edit_description
import manijero.shared.generated.resources.land_list_empty
import manijero.shared.generated.resources.land_list_load_failed
import manijero.shared.generated.resources.land_list_municipality
import manijero.shared.generated.resources.land_list_production
import manijero.shared.generated.resources.land_list_remove
import manijero.shared.generated.resources.land_list_remove_description
import manijero.shared.generated.resources.land_list_retry
import manijero.shared.generated.resources.land_list_water
import manijero.shared.generated.resources.remove_land_removed
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource

private val ContentMaxWidth = 720.dp

/** What the last successful write was, so the list confirms the right thing or nothing at all. */
enum class LandListConfirmation { ADDED, UPDATED, REMOVED }

/**
 * List of the lands saved on this device. It renders whatever [state] it receives and reports every
 * interaction through [onAddLand], [onEditLand], [onRemoveLand], [onBack], or [onRetry]; reading and
 * persistence happen in the caller. Rows stay non-clickable and show the exact saved name plus the
 * few known details, so similar lands stay distinguishable, and each row has its own visible
 * `Editar` control so correcting a land is a labelled, deliberate action. Each row also has its own
 * visible `Eliminar` control, whose accessible description names the exact saved land; selecting it
 * opens the confirmation and writes nothing by itself.
 */
@Composable
fun LandListScreen(
    state: LandListState,
    onAddLand: () -> Unit,
    onEditLand: (Land) -> Unit,
    onRemoveLand: (Land) -> Unit,
    onBack: () -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
    confirmation: LandListConfirmation? = null,
) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 32.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = ContentMaxWidth),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(
                    text = stringResource(Res.string.chat_home_lands),
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                )
                Text(
                    text = stringResource(Res.string.land_list_description),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                val confirmationResource = when (confirmation) {
                    LandListConfirmation.ADDED -> Res.string.add_land_saved
                    LandListConfirmation.UPDATED -> Res.string.edit_land_saved
                    LandListConfirmation.REMOVED -> Res.string.remove_land_removed
                    null -> null
                }
                if (confirmationResource != null) {
                    Text(
                        text = stringResource(confirmationResource),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier
                            .fillMaxWidth()
                            .semantics { liveRegion = LiveRegionMode.Polite },
                    )
                }

                when {
                    state.loadFailed -> Text(
                        text = stringResource(Res.string.land_list_load_failed),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier
                            .fillMaxWidth()
                            .semantics { liveRegion = LiveRegionMode.Polite },
                    )

                    state.isEmpty -> Text(
                        text = stringResource(Res.string.land_list_empty),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )

                    else -> state.lands.forEach { land ->
                        LandRow(
                            land = land,
                            onEdit = { onEditLand(land) },
                            onRemove = { onRemoveLand(land) },
                        )
                    }
                }

                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    if (state.loadFailed) {
                        Button(
                            onClick = onRetry,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(Res.string.land_list_retry))
                        }
                    } else {
                        Button(
                            onClick = onAddLand,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(Res.string.land_list_add))
                        }
                    }
                    TextButton(
                        onClick = onBack,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(Res.string.land_list_back))
                    }
                }
            }
        }
    }
}

/**
 * One saved land. The name and its details are merged into a single node so assistive technology
 * reads them together, while the `Editar` and `Eliminar` controls are their own labelled buttons
 * whose accessible description names the exact saved land. The row card itself is not clickable:
 * reading a row never navigates, and neither control writes anything by itself.
 */
@Composable
private fun LandRow(
    land: Land,
    onEdit: () -> Unit,
    onRemove: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics(mergeDescendants = true) {},
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = land.name,
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                LandDetails(
                    municipality = land.municipality,
                    waterRegime = land.waterRegime,
                    productionMethod = land.productionMethod,
                )
            }
            val editDescription =
                stringResource(Res.string.land_list_edit_description, land.name)
            TextButton(
                onClick = onEdit,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics { contentDescription = editDescription },
            ) {
                Text(stringResource(Res.string.land_list_edit))
            }
            val removeDescription =
                stringResource(Res.string.land_list_remove_description, land.name)
            TextButton(
                onClick = onRemove,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics { contentDescription = removeDescription },
            ) {
                Text(stringResource(Res.string.land_list_remove))
            }
        }
    }
}

/**
 * The known detail lines of one land, shared by the list row and the removal confirmation so a
 * value reads the same in both. It renders no name, id, area, or notes: the caller shows the name
 * itself. An absent municipality is skipped, and an `UNKNOWN` attribute still reads `No lo sé`.
 */
@Composable
internal fun LandDetails(
    municipality: String?,
    waterRegime: WaterRegime,
    productionMethod: ProductionMethod,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        municipality?.takeIf { it.isNotBlank() }?.let { value ->
            LandRowDetail(stringResource(Res.string.land_list_municipality, value))
        }
        LandRowDetail(
            stringResource(
                Res.string.land_list_water,
                stringResource(waterRegimeLabel(waterRegime)),
            ),
        )
        LandRowDetail(
            stringResource(
                Res.string.land_list_production,
                stringResource(productionMethodLabel(productionMethod)),
            ),
        )
    }
}

@Composable
private fun LandRowDetail(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

/** Reuses the form's vocabulary so a value reads the same in the list as in the form. */
private fun waterRegimeLabel(waterRegime: WaterRegime): StringResource = when (waterRegime) {
    WaterRegime.UNKNOWN -> Res.string.add_land_unknown
    WaterRegime.DRYLAND -> Res.string.add_land_water_dryland
    WaterRegime.IRRIGATED -> Res.string.add_land_water_irrigated
    WaterRegime.MIXED -> Res.string.add_land_water_mixed
}

private fun productionMethodLabel(productionMethod: ProductionMethod): StringResource =
    when (productionMethod) {
        ProductionMethod.UNKNOWN -> Res.string.add_land_unknown
        ProductionMethod.CONVENTIONAL -> Res.string.add_land_production_conventional
        ProductionMethod.ORGANIC -> Res.string.add_land_production_organic
        ProductionMethod.MIXED -> Res.string.add_land_production_mixed
    }

private fun previewLand(
    id: String,
    name: String,
    municipality: String? = null,
    waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
) = Land(
    id = id,
    name = name,
    municipality = municipality,
    waterRegime = waterRegime,
    productionMethod = productionMethod,
    createdAtEpochMillis = 0,
    updatedAtEpochMillis = 0,
)

@Preview(name = "Land list — empty")
@Composable
private fun LandListEmptyPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Land list — two distinguishable lands")
@Composable
private fun LandListTwoLandsPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand("land-1", "Los Olivos"),
                    previewLand(
                        "land-2",
                        "La Loma",
                        municipality = "Martos",
                        waterRegime = WaterRegime.IRRIGATED,
                        productionMethod = ProductionMethod.ORGANIC,
                    ),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Land list — duplicate names")
@Composable
private fun LandListDuplicateNamesPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand("land-1", "Los Olivos"),
                    previewLand(
                        "land-2",
                        "Los Olivos",
                        municipality = "Úbeda",
                        waterRegime = WaterRegime.DRYLAND,
                    ),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Land list — many lands")
@Composable
private fun LandListManyLandsPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = (1..8).map { index ->
                    previewLand(
                        id = "land-$index",
                        name = "Terreno $index",
                        municipality = "Municipio $index",
                        waterRegime = WaterRegime.entries[index % WaterRegime.entries.size],
                        productionMethod = ProductionMethod.entries[
                            index % ProductionMethod.entries.size,
                        ],
                    )
                },
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Land list — long text")
@Composable
private fun LandListLongTextPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand(
                        id = "land-1",
                        name = "El olivar de mi abuelo junto al camino de la fuente",
                        municipality = "Villanueva del Arzobispo (Sierra de Cazorla)",
                        waterRegime = WaterRegime.MIXED,
                        productionMethod = ProductionMethod.MIXED,
                    ),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Land list — load failure")
@Composable
private fun LandListLoadFailurePreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(loadFailed = true),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Land list — just saved")
@Composable
private fun LandListJustSavedPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(lands = listOf(previewLand("land-1", "Los Olivos"))),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
            confirmation = LandListConfirmation.ADDED,
        )
    }
}

@Preview(name = "Land list — just updated")
@Composable
private fun LandListJustUpdatedPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(lands = listOf(previewLand("land-1", "Los Olivos corregido"))),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
            confirmation = LandListConfirmation.UPDATED,
        )
    }
}

@Preview(name = "Land list — just removed")
@Composable
private fun LandListJustRemovedPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(lands = listOf(previewLand("land-2", "La Loma"))),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
            confirmation = LandListConfirmation.REMOVED,
        )
    }
}

@Preview(name = "Land list — compact", widthDp = 320)
@Composable
private fun LandListCompactPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(lands = listOf(previewLand("land-1", "Los Olivos"))),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Land list — wide", widthDp = 900)
@Composable
private fun LandListWidePreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(previewLand("land-1", "La Loma", municipality = "Martos")),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Land list — large font", fontScale = 2f)
@Composable
private fun LandListLargeFontPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand(
                        "land-1",
                        "Los Olivos",
                        waterRegime = WaterRegime.IRRIGATED,
                        productionMethod = ProductionMethod.ORGANIC,
                    ),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onBack = {},
            onRetry = {},
        )
    }
}
