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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.add_land_cancel
import manijero.shared.generated.resources.add_land_municipality_label
import manijero.shared.generated.resources.add_land_name_error
import manijero.shared.generated.resources.add_land_name_label
import manijero.shared.generated.resources.add_land_production_conventional
import manijero.shared.generated.resources.add_land_production_label
import manijero.shared.generated.resources.add_land_production_mixed
import manijero.shared.generated.resources.add_land_production_organic
import manijero.shared.generated.resources.add_land_unknown
import manijero.shared.generated.resources.add_land_water_dryland
import manijero.shared.generated.resources.add_land_water_irrigated
import manijero.shared.generated.resources.add_land_water_label
import manijero.shared.generated.resources.add_land_water_mixed
import manijero.shared.generated.resources.edit_land_description
import manijero.shared.generated.resources.edit_land_missing
import manijero.shared.generated.resources.edit_land_save
import manijero.shared.generated.resources.edit_land_save_failed
import manijero.shared.generated.resources.edit_land_title
import org.jetbrains.compose.resources.stringResource

/**
 * Short shared form to correct one land. It renders whatever [state] it receives and reports every
 * interaction through [onAction] or [onCancel]; persistence happens in the caller and only ever
 * targets [EditLandState.landId]. The form is prefilled so the name tells the person which land is
 * being edited, and it deliberately shows no id, area, or notes.
 */
@Composable
fun EditLandScreen(
    state: EditLandState,
    onAction: (EditLandAction) -> Unit,
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
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 720.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(
                    text = stringResource(Res.string.edit_land_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                )
                Text(
                    text = stringResource(Res.string.edit_land_description),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                val nameErrorText: (@Composable () -> Unit)? = if (state.showNameError) {
                    { Text(stringResource(Res.string.add_land_name_error)) }
                } else {
                    null
                }
                OutlinedTextField(
                    value = state.name,
                    onValueChange = { onAction(EditLandAction.NameChanged(it)) },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(stringResource(Res.string.add_land_name_label)) },
                    isError = state.showNameError,
                    supportingText = nameErrorText,
                    singleLine = true,
                )

                OutlinedTextField(
                    value = state.municipality,
                    onValueChange = { onAction(EditLandAction.MunicipalityChanged(it)) },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(stringResource(Res.string.add_land_municipality_label)) },
                    singleLine = true,
                )

                ChoiceGroup(
                    label = stringResource(Res.string.add_land_water_label),
                    choices = listOf(
                        ChoiceItem(
                            label = Res.string.add_land_unknown,
                            selected = state.waterRegime == WaterRegime.UNKNOWN,
                            onSelect = {
                                onAction(
                                    EditLandAction.WaterRegimeSelected(WaterRegime.UNKNOWN),
                                )
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_water_dryland,
                            selected = state.waterRegime == WaterRegime.DRYLAND,
                            onSelect = {
                                onAction(
                                    EditLandAction.WaterRegimeSelected(WaterRegime.DRYLAND),
                                )
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_water_irrigated,
                            selected = state.waterRegime == WaterRegime.IRRIGATED,
                            onSelect = {
                                onAction(
                                    EditLandAction.WaterRegimeSelected(WaterRegime.IRRIGATED),
                                )
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_water_mixed,
                            selected = state.waterRegime == WaterRegime.MIXED,
                            onSelect = {
                                onAction(EditLandAction.WaterRegimeSelected(WaterRegime.MIXED))
                            },
                        ),
                    ),
                )

                ChoiceGroup(
                    label = stringResource(Res.string.add_land_production_label),
                    choices = listOf(
                        ChoiceItem(
                            label = Res.string.add_land_unknown,
                            selected = state.productionMethod == ProductionMethod.UNKNOWN,
                            onSelect = {
                                onAction(
                                    EditLandAction.ProductionMethodSelected(
                                        ProductionMethod.UNKNOWN,
                                    ),
                                )
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_production_conventional,
                            selected = state.productionMethod == ProductionMethod.CONVENTIONAL,
                            onSelect = {
                                onAction(
                                    EditLandAction.ProductionMethodSelected(
                                        ProductionMethod.CONVENTIONAL,
                                    ),
                                )
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_production_organic,
                            selected = state.productionMethod == ProductionMethod.ORGANIC,
                            onSelect = {
                                onAction(
                                    EditLandAction.ProductionMethodSelected(
                                        ProductionMethod.ORGANIC,
                                    ),
                                )
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_production_mixed,
                            selected = state.productionMethod == ProductionMethod.MIXED,
                            onSelect = {
                                onAction(
                                    EditLandAction.ProductionMethodSelected(
                                        ProductionMethod.MIXED,
                                    ),
                                )
                            },
                        ),
                    ),
                )

                val failureMessage = when (state.failure) {
                    EditLandFailure.WRITE_FAILED -> Res.string.edit_land_save_failed
                    EditLandFailure.LAND_MISSING -> Res.string.edit_land_missing
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

                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Button(
                        onClick = { onAction(EditLandAction.SaveClicked) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(Res.string.edit_land_save))
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

private fun previewEditLandState(
    name: String = "Los Olivos",
    municipality: String = "",
    waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    showNameError: Boolean = false,
    failure: EditLandFailure? = null,
) = EditLandState(
    landId = "land-1",
    name = name,
    municipality = municipality,
    waterRegime = waterRegime,
    productionMethod = productionMethod,
    preservedAreaHectares = null,
    preservedNotes = null,
    showNameError = showNameError,
    failure = failure,
)

@Preview(name = "Edit land — prefilled, name only")
@Composable
private fun EditLandPrefilledPreview() {
    ManijeroTheme { EditLandScreen(state = previewEditLandState(), onAction = {}, onCancel = {}) }
}

@Preview(name = "Edit land — prefilled, known values")
@Composable
private fun EditLandKnownValuesPreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                name = "La Loma",
                municipality = "Martos",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — missing name error")
@Composable
private fun EditLandNameErrorPreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(name = "  ", municipality = "Úbeda", showNameError = true),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — write failure")
@Composable
private fun EditLandWriteFailurePreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                name = "La Loma",
                municipality = "Jaén",
                waterRegime = WaterRegime.DRYLAND,
                failure = EditLandFailure.WRITE_FAILED,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — land no longer stored")
@Composable
private fun EditLandMissingPreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                name = "Los Olivos",
                failure = EditLandFailure.LAND_MISSING,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — long text")
@Composable
private fun EditLandLongTextPreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                name = "El olivar de mi abuelo junto al camino de la fuente",
                municipality = "Villanueva del Arzobispo (Sierra de Cazorla)",
                waterRegime = WaterRegime.MIXED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — compact", widthDp = 320)
@Composable
private fun EditLandCompactPreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(municipality = "Martos"),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — wide", widthDp = 900)
@Composable
private fun EditLandWidePreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(municipality = "Martos"),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — large font", fontScale = 2f)
@Composable
private fun EditLandLargeFontPreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}
