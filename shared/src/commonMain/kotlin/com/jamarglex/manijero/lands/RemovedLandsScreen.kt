package com.jamarglex.manijero.lands

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.design.ManijeroScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.land_list_retry
import manijero.shared.generated.resources.removed_lands_back
import manijero.shared.generated.resources.removed_lands_delete
import manijero.shared.generated.resources.removed_lands_delete_description
import manijero.shared.generated.resources.removed_lands_deleted
import manijero.shared.generated.resources.removed_lands_description
import manijero.shared.generated.resources.removed_lands_empty_body
import manijero.shared.generated.resources.removed_lands_empty_title
import manijero.shared.generated.resources.removed_lands_load_failed
import manijero.shared.generated.resources.removed_lands_restore
import manijero.shared.generated.resources.removed_lands_restore_description
import manijero.shared.generated.resources.removed_lands_restore_failed
import manijero.shared.generated.resources.removed_lands_restore_missing
import manijero.shared.generated.resources.removed_lands_restored
import manijero.shared.generated.resources.removed_lands_title
import org.jetbrains.compose.resources.stringResource

/**
 * The "Terrenos eliminados" list: the lands the person moved out of `Mis terrenos`, each with the
 * details the list row shows, a `Restaurar` action, and a `Borrar para siempre` action.
 *
 * It renders whatever [state] it receives and reports every interaction through [onRestore],
 * [onDeletePermanently], [onRetry] and [onBack]; reading and persistence live in the caller. Neither
 * row action writes anything by itself: `Restaurar` restores the row it names, and
 * `Borrar para siempre` only opens the separate confirmation. A successful restore or deletion is
 * confirmed in words, and a refused one never reads as a success. The screen offers its own `Volver`
 * because it is a detail route inside the lands section, not a shell tab.
 */
@Composable
fun RemovedLandsScreen(
    state: RemovedLandsState,
    onBack: () -> Unit,
    onRestore: (RemovedLand) -> Unit,
    onDeletePermanently: (RemovedLand) -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ManijeroScreen(modifier = modifier) {
        Text(
            text = stringResource(Res.string.removed_lands_title),
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.semantics { heading() },
        )
        Text(
            text = stringResource(Res.string.removed_lands_description),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        val confirmationResource = when (state.confirmation) {
            RemovedLandsConfirmation.RESTORED -> Res.string.removed_lands_restored
            RemovedLandsConfirmation.DELETED -> Res.string.removed_lands_deleted
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

        if (!state.loadFailed) {
            val failureResource = when (state.failure) {
                RemovedLandsFailure.WRITE_FAILED -> Res.string.removed_lands_restore_failed
                RemovedLandsFailure.LAND_MISSING -> Res.string.removed_lands_restore_missing
                null -> null
            }
            if (failureResource != null) {
                Text(
                    text = stringResource(failureResource),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics { liveRegion = LiveRegionMode.Polite },
                )
            }
        }

        when {
            state.loadFailed -> {
                Text(
                    text = stringResource(Res.string.removed_lands_load_failed),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics { liveRegion = LiveRegionMode.Polite },
                )
                Button(onClick = onRetry, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(Res.string.land_list_retry))
                }
            }

            state.isEmpty -> RemovedLandsEmpty()

            else -> state.lands.forEach { removed ->
                RemovedLandRow(
                    removed = removed,
                    onRestore = { onRestore(removed) },
                    onDeletePermanently = { onDeletePermanently(removed) },
                )
            }
        }

        TextButton(
            onClick = onBack,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(Res.string.removed_lands_back))
        }
    }
}

/**
 * The empty removed list: one neutral card with a heading and a plain sentence. It is not the
 * `Mis terrenos` empty state, because this list is reached from a land list that already exists.
 */
@Composable
private fun RemovedLandsEmpty(modifier: Modifier = Modifier) {
    ManijeroCard(modifier = modifier, tone = ManijeroCardTone.Tonal) {
        Text(
            text = stringResource(Res.string.removed_lands_empty_title),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Text(
            text = stringResource(Res.string.removed_lands_empty_body),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

/**
 * One removed land. The name and its details are merged into a single node so assistive technology
 * reads them together, while `Restaurar` and `Borrar para siempre` are their own labelled controls
 * whose accessible description names the exact saved land. The card itself is not clickable.
 */
@Composable
private fun RemovedLandRow(
    removed: RemovedLand,
    onRestore: () -> Unit,
    onDeletePermanently: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ManijeroCard(modifier = modifier, tone = ManijeroCardTone.Outlined) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics(mergeDescendants = true) {},
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = removed.land.name,
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                LandDetails(
                    zone = removed.land.zone,
                    municipality = removed.land.municipality,
                    variety = removed.land.variety,
                    varietyOther = removed.land.varietyOther,
                    areaHectares = removed.land.areaHectares,
                    treeCount = removed.land.treeCount,
                    waterRegime = removed.land.waterRegime,
                    productionMethod = removed.land.productionMethod,
                )
            }
            val restoreDescription =
                stringResource(Res.string.removed_lands_restore_description, removed.land.name)
            TextButton(
                onClick = onRestore,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics { contentDescription = restoreDescription },
            ) {
                Text(stringResource(Res.string.removed_lands_restore))
            }
            val deleteDescription =
                stringResource(Res.string.removed_lands_delete_description, removed.land.name)
            TextButton(
                onClick = onDeletePermanently,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics { contentDescription = deleteDescription },
                colors = ButtonDefaults.textButtonColors(
                    contentColor = MaterialTheme.colorScheme.error,
                ),
            ) {
                Text(stringResource(Res.string.removed_lands_delete))
            }
        }
    }
}

@Suppress("LongParameterList")
private fun previewRemovedLand(
    id: String,
    name: String,
    zone: String = "El Llano",
    municipality: String? = null,
    variety: LandVariety = LandVariety.UNKNOWN,
    varietyOther: String? = null,
    areaHectares: Double? = null,
    treeCount: Int? = null,
    waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
) = RemovedLand(
    land = Land(
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
    ),
    removedAtEpochMillis = 0,
)

@Preview(name = "Removed lands — empty")
@Composable
private fun RemovedLandsEmptyPreview() {
    ManijeroTheme {
        RemovedLandsScreen(
            state = RemovedLandsState(),
            onBack = {},
            onRestore = {},
            onDeletePermanently = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Removed lands — two lands")
@Composable
private fun RemovedLandsTwoLandsPreview() {
    ManijeroTheme {
        RemovedLandsScreen(
            state = RemovedLandsState(
                lands = listOf(
                    previewRemovedLand(
                        id = "land-1",
                        name = "Los Olivos",
                        zone = "Camino de la Fuente",
                        municipality = "Martos",
                        variety = LandVariety.PICUAL,
                        areaHectares = 1.5,
                        treeCount = 85,
                        waterRegime = WaterRegime.DRYLAND,
                        productionMethod = ProductionMethod.ORGANIC,
                    ),
                    previewRemovedLand(
                        id = "land-2",
                        name = "La Loma",
                        zone = "Linde del arroyo",
                        municipality = "Úbeda",
                        variety = LandVariety.OTHER,
                        varietyOther = "Royal de Cazorla",
                        waterRegime = WaterRegime.IRRIGATED,
                    ),
                ),
            ),
            onBack = {},
            onRestore = {},
            onDeletePermanently = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Removed lands — just restored")
@Composable
private fun RemovedLandsRestoredPreview() {
    ManijeroTheme {
        RemovedLandsScreen(
            state = RemovedLandsState(
                lands = listOf(previewRemovedLand("land-2", "La Loma")),
                confirmation = RemovedLandsConfirmation.RESTORED,
            ),
            onBack = {},
            onRestore = {},
            onDeletePermanently = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Removed lands — restore failed")
@Composable
private fun RemovedLandsRestoreFailedPreview() {
    ManijeroTheme {
        RemovedLandsScreen(
            state = RemovedLandsState(
                lands = listOf(previewRemovedLand("land-1", "Los Olivos")),
                failure = RemovedLandsFailure.WRITE_FAILED,
            ),
            onBack = {},
            onRestore = {},
            onDeletePermanently = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Removed lands — load failure")
@Composable
private fun RemovedLandsLoadFailurePreview() {
    ManijeroTheme {
        RemovedLandsScreen(
            state = RemovedLandsState(loadFailed = true),
            onBack = {},
            onRestore = {},
            onDeletePermanently = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Removed lands — long text", widthDp = 320)
@Composable
private fun RemovedLandsLongTextPreview() {
    ManijeroTheme {
        RemovedLandsScreen(
            state = RemovedLandsState(
                lands = listOf(
                    previewRemovedLand(
                        id = "land-1",
                        name = "El olivar de mi abuelo junto al camino de la fuente",
                        zone = "Paraje de la Fuente del Roble, junto al cortijo viejo",
                        municipality = "Villanueva del Arzobispo (Sierra de Cazorla)",
                        variety = LandVariety.OTHER,
                        varietyOther = "Royal de Cazorla",
                        areaHectares = 12.75,
                        treeCount = 1250,
                        waterRegime = WaterRegime.MIXED,
                        productionMethod = ProductionMethod.MIXED,
                    ),
                ),
            ),
            onBack = {},
            onRestore = {},
            onDeletePermanently = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Removed lands — wide", widthDp = 900)
@Composable
private fun RemovedLandsWidePreview() {
    ManijeroTheme {
        RemovedLandsScreen(
            state = RemovedLandsState(
                lands = listOf(previewRemovedLand("land-1", "La Loma", municipality = "Martos")),
            ),
            onBack = {},
            onRestore = {},
            onDeletePermanently = {},
            onRetry = {},
        )
    }
}

@Preview(name = "Removed lands — large font", fontScale = 2f)
@Composable
private fun RemovedLandsLargeFontPreview() {
    ManijeroTheme {
        RemovedLandsScreen(
            state = RemovedLandsState(
                lands = listOf(
                    previewRemovedLand(
                        "land-1",
                        "Los Olivos",
                        waterRegime = WaterRegime.IRRIGATED,
                        productionMethod = ProductionMethod.ORGANIC,
                    ),
                ),
            ),
            onBack = {},
            onRestore = {},
            onDeletePermanently = {},
            onRetry = {},
        )
    }
}
