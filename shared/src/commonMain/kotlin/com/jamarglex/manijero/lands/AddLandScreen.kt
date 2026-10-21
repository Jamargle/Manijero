package com.jamarglex.manijero.lands

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.error
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.add_land_cancel
import manijero.shared.generated.resources.add_land_choice_description
import manijero.shared.generated.resources.add_land_description
import manijero.shared.generated.resources.add_land_municipality_label
import manijero.shared.generated.resources.add_land_name_error
import manijero.shared.generated.resources.add_land_name_label
import manijero.shared.generated.resources.add_land_production_conventional
import manijero.shared.generated.resources.add_land_production_label
import manijero.shared.generated.resources.add_land_production_mixed
import manijero.shared.generated.resources.add_land_production_organic
import manijero.shared.generated.resources.add_land_save
import manijero.shared.generated.resources.add_land_save_failed
import manijero.shared.generated.resources.add_land_title
import manijero.shared.generated.resources.add_land_unknown
import manijero.shared.generated.resources.add_land_water_dryland
import manijero.shared.generated.resources.add_land_water_irrigated
import manijero.shared.generated.resources.add_land_water_label
import manijero.shared.generated.resources.add_land_water_mixed
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource

/**
 * Short shared form to add one land. It renders whatever [state] it receives and reports every
 * interaction through [onAction] or [onCancel]; persistence happens in the caller.
 */
@Composable
fun AddLandScreen(
    state: AddLandState,
    onAction: (AddLandAction) -> Unit,
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
                    text = stringResource(Res.string.add_land_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                    // The form title is the one heading semantic on this surface.
                    modifier = Modifier.semantics { heading() },
                )
                Text(
                    text = stringResource(Res.string.add_land_description),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                // The name field is the only required input, so a blank-name save must both say what
                // is wrong and put input focus back on the field. The focus is requested from the save
                // path (not from a state-keyed effect), because the error flag stays true across a
                // repeated blank attempt and the second press must re-focus the field too.
                val nameFocus = remember { FocusRequester() }
                val nameErrorMessage = stringResource(Res.string.add_land_name_error)
                val handleAction: (AddLandAction) -> Unit = { action ->
                    if (action is AddLandAction.SaveClicked && !state.hasName) {
                        nameFocus.requestFocus()
                    }
                    onAction(action)
                }
                val nameErrorText: (@Composable () -> Unit)? = if (state.showNameError) {
                    {
                        Text(
                            text = nameErrorMessage,
                            modifier = Modifier.semantics {
                                liveRegion = LiveRegionMode.Polite
                            },
                        )
                    }
                } else {
                    null
                }
                OutlinedTextField(
                    value = state.name,
                    onValueChange = { handleAction(AddLandAction.NameChanged(it)) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .focusRequester(nameFocus)
                        .semantics { if (state.showNameError) error(nameErrorMessage) },
                    label = { Text(stringResource(Res.string.add_land_name_label)) },
                    isError = state.showNameError,
                    supportingText = nameErrorText,
                    singleLine = true,
                )

                OutlinedTextField(
                    value = state.municipality,
                    onValueChange = { onAction(AddLandAction.MunicipalityChanged(it)) },
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
                                onAction(AddLandAction.WaterRegimeSelected(WaterRegime.UNKNOWN))
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_water_dryland,
                            selected = state.waterRegime == WaterRegime.DRYLAND,
                            onSelect = {
                                onAction(AddLandAction.WaterRegimeSelected(WaterRegime.DRYLAND))
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_water_irrigated,
                            selected = state.waterRegime == WaterRegime.IRRIGATED,
                            onSelect = {
                                onAction(AddLandAction.WaterRegimeSelected(WaterRegime.IRRIGATED))
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_water_mixed,
                            selected = state.waterRegime == WaterRegime.MIXED,
                            onSelect = {
                                onAction(AddLandAction.WaterRegimeSelected(WaterRegime.MIXED))
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
                                    AddLandAction.ProductionMethodSelected(ProductionMethod.UNKNOWN),
                                )
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_production_conventional,
                            selected = state.productionMethod == ProductionMethod.CONVENTIONAL,
                            onSelect = {
                                onAction(
                                    AddLandAction.ProductionMethodSelected(
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
                                    AddLandAction.ProductionMethodSelected(ProductionMethod.ORGANIC),
                                )
                            },
                        ),
                        ChoiceItem(
                            label = Res.string.add_land_production_mixed,
                            selected = state.productionMethod == ProductionMethod.MIXED,
                            onSelect = {
                                onAction(
                                    AddLandAction.ProductionMethodSelected(ProductionMethod.MIXED),
                                )
                            },
                        ),
                    ),
                )

                if (state.showSaveError) {
                    Text(
                        text = stringResource(Res.string.add_land_save_failed),
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
                        onClick = { handleAction(AddLandAction.SaveClicked) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(Res.string.add_land_save))
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

internal data class ChoiceItem(
    val label: StringResource,
    val selected: Boolean,
    val onSelect: () -> Unit,
)

@Composable
internal fun ChoiceGroup(
    label: String,
    choices: List<ChoiceItem>,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onBackground,
        )
        // The rows are one single-choice set, and each row names its own group ("Riego: No lo sé",
        // "Producción: No lo sé"), so two identically worded options can never be confused when read
        // aloud. The label stays outside the group and no row gains a second focus stop: the selected
        // state, role, and click still come from the single `selectable` on the row.
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .selectableGroup(),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            choices.forEach { choice ->
                val optionName = stringResource(
                    Res.string.add_land_choice_description,
                    label,
                    stringResource(choice.label),
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .selectable(
                            selected = choice.selected,
                            role = Role.RadioButton,
                            onClick = choice.onSelect,
                        )
                        .semantics { contentDescription = optionName }
                        .padding(vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RadioButton(selected = choice.selected, onClick = null)
                    Text(
                        text = stringResource(choice.label),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onBackground,
                        modifier = Modifier.padding(start = 12.dp),
                    )
                }
            }
        }
    }
}

@Preview(name = "Add land — blank")
@Composable
private fun AddLandBlankPreview() {
    ManijeroTheme { AddLandScreen(state = AddLandState(), onAction = {}, onCancel = {}) }
}

@Preview(name = "Add land — missing name error")
@Composable
private fun AddLandNameErrorPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(municipality = "Úbeda", showNameError = true),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Add land — known values")
@Composable
private fun AddLandKnownValuesPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(
                name = "Los Olivos",
                municipality = "Martos",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Add land — save failure")
@Composable
private fun AddLandSaveErrorPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(
                name = "La Loma",
                municipality = "Jaén",
                waterRegime = WaterRegime.DRYLAND,
                showSaveError = true,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Add land — long text")
@Composable
private fun AddLandLongTextPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(
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

@Preview(name = "Add land — compact", widthDp = 360)
@Composable
private fun AddLandCompactPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(name = "Los Olivos"),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Add land — wide", widthDp = 900)
@Composable
private fun AddLandWidePreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(name = "Los Olivos", municipality = "Martos"),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Add land — large font", fontScale = 2f)
@Composable
private fun AddLandLargeFontPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(
                name = "Los Olivos",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Add land — narrow, large font, name error", widthDp = 320, fontScale = 2f)
@Composable
private fun AddLandNarrowLargeFontNameErrorPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(municipality = "Úbeda", showNameError = true),
            onAction = {},
            onCancel = {},
        )
    }
}
