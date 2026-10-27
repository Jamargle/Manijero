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
import manijero.shared.generated.resources.add_land_cancel
import manijero.shared.generated.resources.permanently_delete_land_action
import manijero.shared.generated.resources.permanently_delete_land_action_description
import manijero.shared.generated.resources.permanently_delete_land_confirm
import manijero.shared.generated.resources.permanently_delete_land_failed
import manijero.shared.generated.resources.permanently_delete_land_missing
import manijero.shared.generated.resources.permanently_delete_land_title
import org.jetbrains.compose.resources.stringResource

/**
 * The second confirmation for deleting one removed land for good. It renders whatever [state] it
 * receives and reports the two deliberate choices through [onDelete] and [onCancel]; the deletion
 * happens in the caller and only ever targets [PermanentlyDeleteLandState.landId].
 *
 * The screen names the exact saved land and repeats the same known details the removed-list row
 * shows, so two same-named lands stay distinguishable, and it shows no id, notes, or removal date.
 * Reaching this screen writes nothing; the first confirmation was moving the land out of
 * `Mis terrenos`, and this one is the only place a record can leave the device for good.
 */
@Composable
fun PermanentlyDeleteLandScreen(
    state: PermanentlyDeleteLandState,
    onDelete: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ManijeroScreen(modifier = modifier) {
        Text(
            text = stringResource(Res.string.permanently_delete_land_title),
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.semantics { heading() },
        )
        Text(
            text = stringResource(Res.string.permanently_delete_land_confirm, state.name),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        // The known details are the same lines the row shows, merged into one node so the deletion
        // target reads as a single item. The name appears once, in the sentence above.
        ManijeroCard(tone = ManijeroCardTone.Danger) {
            Column(
                modifier = Modifier.semantics(mergeDescendants = true) {},
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
        }

        val failureMessage = when (state.failure) {
            PermanentlyDeleteFailure.WRITE_FAILED -> Res.string.permanently_delete_land_failed
            PermanentlyDeleteFailure.LAND_MISSING -> Res.string.permanently_delete_land_missing
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
        // together with its text label, so it is never signalled by colour alone. Its accessible
        // description names the same land the confirmation sentence names. Cancelar is the secondary
        // back control and writes nothing.
        val deleteDescription =
            stringResource(Res.string.permanently_delete_land_action_description, state.name)
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Button(
                onClick = onDelete,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        contentDescription = deleteDescription
                    },
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error,
                    contentColor = MaterialTheme.colorScheme.onError,
                ),
            ) {
                Text(stringResource(Res.string.permanently_delete_land_action))
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

@Suppress("LongParameterList")
private fun previewPermanentlyDeleteLandState(
    name: String = "Los Olivos",
    zone: String = "Camino de la Fuente",
    municipality: String? = null,
    variety: LandVariety = LandVariety.UNKNOWN,
    varietyOther: String? = null,
    areaHectares: Double? = null,
    treeCount: Int? = null,
    waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    failure: PermanentlyDeleteFailure? = null,
) = PermanentlyDeleteLandState(
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

@Preview(name = "Permanently delete land — name only")
@Composable
private fun PermanentlyDeleteLandNameOnlyPreview() {
    ManijeroTheme {
        PermanentlyDeleteLandScreen(
            state = previewPermanentlyDeleteLandState(),
            onDelete = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Permanently delete land — known details")
@Composable
private fun PermanentlyDeleteLandKnownDetailsPreview() {
    ManijeroTheme {
        PermanentlyDeleteLandScreen(
            state = previewPermanentlyDeleteLandState(
                name = "La Loma",
                zone = "Linde del arroyo",
                municipality = "Martos",
                variety = LandVariety.PICUAL,
                areaHectares = 2.5,
                treeCount = 85,
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            onDelete = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Permanently delete land — write failure")
@Composable
private fun PermanentlyDeleteLandWriteFailurePreview() {
    ManijeroTheme {
        PermanentlyDeleteLandScreen(
            state = previewPermanentlyDeleteLandState(
                name = "La Loma",
                municipality = "Jaén",
                waterRegime = WaterRegime.DRYLAND,
                failure = PermanentlyDeleteFailure.WRITE_FAILED,
            ),
            onDelete = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Permanently delete land — land no longer removed")
@Composable
private fun PermanentlyDeleteLandMissingPreview() {
    ManijeroTheme {
        PermanentlyDeleteLandScreen(
            state = previewPermanentlyDeleteLandState(
                name = "Los Olivos",
                failure = PermanentlyDeleteFailure.LAND_MISSING,
            ),
            onDelete = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Permanently delete land — compact", widthDp = 320)
@Composable
private fun PermanentlyDeleteLandCompactPreview() {
    ManijeroTheme {
        PermanentlyDeleteLandScreen(
            state = previewPermanentlyDeleteLandState(name = "La Loma", municipality = "Martos"),
            onDelete = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Permanently delete land — large font", fontScale = 2f)
@Composable
private fun PermanentlyDeleteLandLargeFontPreview() {
    ManijeroTheme {
        PermanentlyDeleteLandScreen(
            state = previewPermanentlyDeleteLandState(
                name = "La Loma",
                zone = "Linde del arroyo",
                municipality = "Martos",
                variety = LandVariety.ARBEQUINA,
                areaHectares = 12.75,
                treeCount = 1250,
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            onDelete = {},
            onCancel = {},
        )
    }
}
