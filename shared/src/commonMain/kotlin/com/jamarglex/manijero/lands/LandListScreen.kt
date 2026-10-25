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
import androidx.compose.ui.Alignment
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
import manijero.shared.generated.resources.land_list_description
import manijero.shared.generated.resources.land_list_edit
import manijero.shared.generated.resources.land_list_edit_description
import manijero.shared.generated.resources.land_list_empty
import manijero.shared.generated.resources.land_list_load_failed
import manijero.shared.generated.resources.add_land_variety_other
import manijero.shared.generated.resources.land_list_municipality
import manijero.shared.generated.resources.land_list_production
import manijero.shared.generated.resources.land_list_remove
import manijero.shared.generated.resources.land_list_remove_description
import manijero.shared.generated.resources.land_list_retry
import manijero.shared.generated.resources.land_list_surface
import manijero.shared.generated.resources.land_list_trees
import manijero.shared.generated.resources.land_list_variety
import manijero.shared.generated.resources.land_list_water
import manijero.shared.generated.resources.land_list_zone
import manijero.shared.generated.resources.remove_land_removed
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource

private val ContentMaxWidth = 720.dp

/** What the last successful write was, so the list confirms the right thing or nothing at all. */
enum class LandListConfirmation { ADDED, UPDATED, REMOVED }

/**
 * List of the lands saved on this device. It renders whatever [state] it receives and reports every
 * interaction through [onAddLand], [onEditLand], [onRemoveLand], or [onRetry]; reading and
 * persistence happen in the caller. Top-level navigation is the app shell's job, so this screen
 * offers no `Volver`; the tabs are the way back. Rows stay non-clickable and show the exact saved name plus the
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
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Column(
                modifier = Modifier
                    .widthIn(max = ContentMaxWidth)
                    .fillMaxWidth(),
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
        color = MaterialTheme.colorScheme.surfaceContainerLowest,
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
                    zone = land.zone,
                    municipality = land.municipality,
                    variety = land.variety,
                    varietyOther = land.varietyOther,
                    areaHectares = land.areaHectares,
                    treeCount = land.treeCount,
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
 * The known detail lines of one land, shared by the list row, the removal confirmation and the
 * clarification chooser so a value reads the same everywhere. It renders no name, id or notes: the
 * caller shows the name itself. A missing zone (a legacy record), municipality, surface or tree
 * count is omitted, never shown as zero or guessed; an `UNKNOWN` attribute reads `No lo sé`.
 */
@Suppress("LongParameterList")
@Composable
internal fun LandDetails(
    zone: String?,
    municipality: String?,
    variety: LandVariety,
    varietyOther: String?,
    areaHectares: Double?,
    treeCount: Int?,
    waterRegime: WaterRegime,
    productionMethod: ProductionMethod,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        zone?.takeIf { it.isNotBlank() }?.let { value ->
            LandRowDetail(stringResource(Res.string.land_list_zone, value))
        }
        municipality?.takeIf { it.isNotBlank() }?.let { value ->
            LandRowDetail(stringResource(Res.string.land_list_municipality, value))
        }
        val varietyValue = when (variety) {
            LandVariety.OTHER -> varietyOther?.takeIf { it.isNotBlank() }
                ?: stringResource(Res.string.add_land_variety_other)

            else -> stringResource(landVarietyLabel(variety))
        }
        LandRowDetail(stringResource(Res.string.land_list_variety, varietyValue))
        areaHectares?.let { value ->
            LandRowDetail(
                stringResource(Res.string.land_list_surface, formatHectares(value)),
            )
        }
        treeCount?.let { value ->
            LandRowDetail(stringResource(Res.string.land_list_trees, formatTreeCount(value)))
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

@Suppress("LongParameterList")
private fun previewLand(
    id: String,
    name: String,
    zone: String? = null,
    municipality: String? = null,
    variety: LandVariety = LandVariety.UNKNOWN,
    varietyOther: String? = null,
    areaHectares: Double? = null,
    treeCount: Int? = null,
    waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
) = Land(
    id = id,
    name = name,
    zone = zone,
    municipality = municipality,
    variety = variety,
    varietyOther = varietyOther,
    areaHectares = areaHectares,
    treeCount = treeCount,
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
                    previewLand(
                        "land-1",
                        "Los Olivos",
                        zone = "Camino de la Fuente",
                        municipality = "Martos",
                        variety = LandVariety.PICUAL,
                        areaHectares = 1.5,
                        treeCount = 85,
                        waterRegime = WaterRegime.DRYLAND,
                        productionMethod = ProductionMethod.ORGANIC,
                    ),
                    previewLand(
                        "land-2",
                        "La Loma",
                        zone = "Linde del arroyo",
                        municipality = "Úbeda",
                        variety = LandVariety.OTHER,
                        varietyOther = "Royal de Cazorla",
                        waterRegime = WaterRegime.IRRIGATED,
                    ),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
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
                    previewLand("land-1", "Los Olivos", zone = "El Llano"),
                    previewLand(
                        "land-2",
                        "Los Olivos",
                        zone = "Las Eras",
                        municipality = "Úbeda",
                        waterRegime = WaterRegime.DRYLAND,
                    ),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
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
            onRetry = {},
        )
    }
}
