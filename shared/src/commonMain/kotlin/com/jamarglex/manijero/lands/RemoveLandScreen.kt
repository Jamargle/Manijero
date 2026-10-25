package com.jamarglex.manijero.lands

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.add_land_cancel
import manijero.shared.generated.resources.remove_land_confirm
import manijero.shared.generated.resources.remove_land_failed
import manijero.shared.generated.resources.remove_land_missing
import manijero.shared.generated.resources.remove_land_remove
import manijero.shared.generated.resources.remove_land_title
import org.jetbrains.compose.resources.stringResource

/**
 * Confirmation step for removing one land. It renders whatever [state] it receives and reports the
 * two deliberate choices through [onRemove] and [onCancel]; the deletion happens in the caller and
 * only ever targets [RemoveLandState.landId]. The screen names the exact saved land and repeats the
 * same known details the list row shows, so two same-named lands stay distinguishable, and it
 * shows no id or notes.
 */
@Composable
fun RemoveLandScreen(
    state: RemoveLandState,
    onRemove: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
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
                    .widthIn(max = 720.dp)
                    .fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(
                    text = stringResource(Res.string.remove_land_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                )
                Text(
                    text = stringResource(Res.string.remove_land_confirm, state.name),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                // The known details are the same lines the row shows, merged into one node so the
                // removal target reads as a single item. The name appears once, in the sentence above.
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics(mergeDescendants = true) {},
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    LandDetails(
                        zone = state.zone,
                        municipality = state.municipality,
                        variety = state.variety,
                        varietyOther = state.varietyOther,
                        areaHectares = state.areaHectares,
                        treeCount = state.treeCount,
                        waterRegime = state.waterRegime,
                        productionMethod = state.productionMethod,
                    )
                }

                val failureMessage = when (state.failure) {
                    RemoveLandFailure.WRITE_FAILED -> Res.string.remove_land_failed
                    RemoveLandFailure.LAND_MISSING -> Res.string.remove_land_missing
                    null -> null
                }
                if (failureMessage != null) {
                    Text(
                        text = stringResource(failureMessage),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier
                            .fillMaxWidth()
                            .semantics { liveRegion = LiveRegionMode.Polite },
                    )
                }

                // The destructive choice is the one primary action and carries the themed danger pair
                // together with its text label, so it is never signalled by colour alone. Cancelar is
                // the secondary back control and writes nothing.
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Button(
                        onClick = onRemove,
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.error,
                            contentColor = MaterialTheme.colorScheme.onError,
                        ),
                    ) {
                        Text(stringResource(Res.string.remove_land_remove))
                    }
                    TextButton(
                        onClick = onCancel,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(Res.string.add_land_cancel))
                    }
                }
            }
        }
    }
}

@Suppress("LongParameterList")
private fun previewRemoveLandState(
    name: String = "Los Olivos",
    zone: String = "Camino de la Fuente",
    municipality: String? = null,
    variety: LandVariety = LandVariety.UNKNOWN,
    varietyOther: String? = null,
    areaHectares: Double? = null,
    treeCount: Int? = null,
    waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    failure: RemoveLandFailure? = null,
) = RemoveLandState(
    landId = "land-1",
    name = name,
    zone = zone,
    municipality = municipality,
    waterRegime = waterRegime,
    productionMethod = productionMethod,
    variety = variety,
    varietyOther = varietyOther,
    areaHectares = areaHectares,
    treeCount = treeCount,
    failure = failure,
)

@Preview(name = "Remove land — name only")
@Composable
private fun RemoveLandNameOnlyPreview() {
    ManijeroTheme {
        RemoveLandScreen(state = previewRemoveLandState(), onRemove = {}, onCancel = {})
    }
}

@Preview(name = "Remove land — known details")
@Composable
private fun RemoveLandKnownDetailsPreview() {
    ManijeroTheme {
        RemoveLandScreen(
            state = previewRemoveLandState(
                name = "La Loma",
                zone = "Linde del arroyo",
                municipality = "Martos",
                variety = LandVariety.PICUAL,
                areaHectares = 2.5,
                treeCount = 85,
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            onRemove = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Remove land — long text")
@Composable
private fun RemoveLandLongTextPreview() {
    ManijeroTheme {
        RemoveLandScreen(
            state = previewRemoveLandState(
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
            onRemove = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Remove land — write failure")
@Composable
private fun RemoveLandWriteFailurePreview() {
    ManijeroTheme {
        RemoveLandScreen(
            state = previewRemoveLandState(
                name = "La Loma",
                municipality = "Jaén",
                waterRegime = WaterRegime.DRYLAND,
                failure = RemoveLandFailure.WRITE_FAILED,
            ),
            onRemove = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Remove land — land no longer stored")
@Composable
private fun RemoveLandMissingPreview() {
    ManijeroTheme {
        RemoveLandScreen(
            state = previewRemoveLandState(
                name = "Los Olivos",
                failure = RemoveLandFailure.LAND_MISSING,
            ),
            onRemove = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Remove land — compact", widthDp = 320)
@Composable
private fun RemoveLandCompactPreview() {
    ManijeroTheme {
        RemoveLandScreen(
            state = previewRemoveLandState(name = "La Loma", municipality = "Martos"),
            onRemove = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Remove land — wide", widthDp = 900)
@Composable
private fun RemoveLandWidePreview() {
    ManijeroTheme {
        RemoveLandScreen(
            state = previewRemoveLandState(name = "La Loma", municipality = "Martos"),
            onRemove = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Remove land — large font", fontScale = 2f)
@Composable
private fun RemoveLandLargeFontPreview() {
    ManijeroTheme {
        RemoveLandScreen(
            state = previewRemoveLandState(
                name = "La Loma",
                zone = "Linde del arroyo",
                municipality = "Martos",
                variety = LandVariety.ARBEQUINA,
                areaHectares = 12.75,
                treeCount = 1250,
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            onRemove = {},
            onCancel = {},
        )
    }
}
