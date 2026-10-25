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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.design.ManijeroDropdownField
import com.jamarglex.manijero.design.ManijeroMeasureField
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
import manijero.shared.generated.resources.add_land_surface_error
import manijero.shared.generated.resources.add_land_surface_help
import manijero.shared.generated.resources.add_land_surface_label
import manijero.shared.generated.resources.add_land_title
import manijero.shared.generated.resources.add_land_trees_error
import manijero.shared.generated.resources.add_land_trees_help
import manijero.shared.generated.resources.add_land_trees_label
import manijero.shared.generated.resources.add_land_unknown
import manijero.shared.generated.resources.add_land_variety_arbequina
import manijero.shared.generated.resources.add_land_variety_gordal
import manijero.shared.generated.resources.add_land_variety_help
import manijero.shared.generated.resources.add_land_variety_hojiblanca
import manijero.shared.generated.resources.add_land_variety_label
import manijero.shared.generated.resources.add_land_variety_lechin_de_sevilla
import manijero.shared.generated.resources.add_land_variety_manzanilla
import manijero.shared.generated.resources.add_land_variety_mixed
import manijero.shared.generated.resources.add_land_variety_other
import manijero.shared.generated.resources.add_land_variety_other_error
import manijero.shared.generated.resources.add_land_variety_other_help
import manijero.shared.generated.resources.add_land_variety_other_label
import manijero.shared.generated.resources.add_land_variety_other_too_long
import manijero.shared.generated.resources.add_land_variety_picual
import manijero.shared.generated.resources.add_land_variety_picudo
import manijero.shared.generated.resources.add_land_water_dryland
import manijero.shared.generated.resources.add_land_water_irrigated
import manijero.shared.generated.resources.add_land_water_label
import manijero.shared.generated.resources.add_land_water_mixed
import manijero.shared.generated.resources.add_land_zone_error
import manijero.shared.generated.resources.add_land_zone_help
import manijero.shared.generated.resources.add_land_zone_label
import manijero.shared.generated.resources.add_land_zone_too_long
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource

/**
 * Short shared form to add one land. It renders whatever [state] it receives and reports every
 * interaction through [onAction] or [onCancel]; persistence happens in the caller.
 *
 * Name and zone are required and say so in words. Variety, custom variety, surface and olive-tree
 * count are optional; leaving them blank stores an absent value, never a zero or a guess. Saving
 * with one or more invalid fields writes nothing and moves focus to the first invalid one, in the
 * same order the fields are laid out.
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

                // Focus is requested from the save path (not from a state-keyed effect), because an
                // error flag stays true across a repeated invalid attempt and each press must
                // re-focus the first field that still needs attention.
                val nameFocus = remember { FocusRequester() }
                val zoneFocus = remember { FocusRequester() }
                val varietyOtherFocus = remember { FocusRequester() }
                val areaFocus = remember { FocusRequester() }
                val treeCountFocus = remember { FocusRequester() }
                val handleAction: (AddLandAction) -> Unit = { action ->
                    if (action is AddLandAction.SaveClicked) {
                        when {
                            !state.hasName -> nameFocus.requestFocus()
                            state.zoneIssue != null -> zoneFocus.requestFocus()
                            !state.varietyOtherValid -> varietyOtherFocus.requestFocus()
                            !state.areaMeasure.isValid -> areaFocus.requestFocus()
                            !state.treeCountMeasure.isValid -> treeCountFocus.requestFocus()
                        }
                    }
                    onAction(action)
                }

                val nameErrorMessage = stringResource(Res.string.add_land_name_error)
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

                val zoneErrorMessage = when (state.zoneIssue) {
                    ZoneProblem.BLANK -> stringResource(Res.string.add_land_zone_error)
                    ZoneProblem.TOO_LONG -> stringResource(Res.string.add_land_zone_too_long)
                    null -> null
                }
                val zoneHelp = stringResource(Res.string.add_land_zone_help)
                val zoneSupportingText: (@Composable () -> Unit)? = when {
                    state.showZoneError && zoneErrorMessage != null -> {
                        {
                            Text(
                                text = zoneErrorMessage,
                                modifier = Modifier.semantics {
                                    liveRegion = LiveRegionMode.Polite
                                },
                            )
                        }
                    }

                    else -> {
                        { Text(text = zoneHelp) }
                    }
                }
                OutlinedTextField(
                    value = state.zone,
                    onValueChange = { handleAction(AddLandAction.ZoneChanged(it)) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .focusRequester(zoneFocus)
                        .semantics {
                            if (state.showZoneError && zoneErrorMessage != null) {
                                error(zoneErrorMessage)
                            }
                        },
                    label = { Text(stringResource(Res.string.add_land_zone_label)) },
                    isError = state.showZoneError,
                    supportingText = zoneSupportingText,
                    singleLine = true,
                )

                OutlinedTextField(
                    value = state.municipality,
                    onValueChange = { onAction(AddLandAction.MunicipalityChanged(it)) },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(stringResource(Res.string.add_land_municipality_label)) },
                    singleLine = true,
                )

                val varietyOptions = LAND_VARIETY_OPTIONS.map { stringResource(landVarietyLabel(it)) }
                ManijeroDropdownField(
                    label = stringResource(Res.string.add_land_variety_label),
                    options = varietyOptions,
                    selected = stringResource(landVarietyLabel(state.variety)),
                    onSelect = { chosen ->
                        val index = varietyOptions.indexOf(chosen)
                        if (index >= 0) {
                            handleAction(AddLandAction.VarietySelected(LAND_VARIETY_OPTIONS[index]))
                        }
                    },
                    supportingText = stringResource(Res.string.add_land_variety_help),
                )

                if (state.variety == LandVariety.OTHER) {
                    val varietyOtherErrorMessage = when {
                        state.varietyOther.isBlank() ->
                            stringResource(Res.string.add_land_variety_other_error)

                        else -> stringResource(Res.string.add_land_variety_other_too_long)
                    }
                    val varietyOtherHelp = stringResource(Res.string.add_land_variety_other_help)
                    val varietyOtherSupportingText: (@Composable () -> Unit)? =
                        if (state.showVarietyOtherError) {
                            {
                                Text(
                                    text = varietyOtherErrorMessage,
                                    modifier = Modifier.semantics {
                                        liveRegion = LiveRegionMode.Polite
                                    },
                                )
                            }
                        } else {
                            { Text(text = varietyOtherHelp) }
                        }
                    OutlinedTextField(
                        value = state.varietyOther,
                        onValueChange = { handleAction(AddLandAction.VarietyOtherChanged(it)) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .focusRequester(varietyOtherFocus)
                            .semantics {
                                if (state.showVarietyOtherError) {
                                    error(varietyOtherErrorMessage)
                                }
                            },
                        label = { Text(stringResource(Res.string.add_land_variety_other_label)) },
                        isError = state.showVarietyOtherError,
                        supportingText = varietyOtherSupportingText,
                        singleLine = true,
                    )
                }

                ManijeroMeasureField(
                    value = state.areaText,
                    onValueChange = { handleAction(AddLandAction.AreaChanged(it)) },
                    label = stringResource(Res.string.add_land_surface_label),
                    modifier = Modifier.focusRequester(areaFocus),
                    supportingText = stringResource(Res.string.add_land_surface_help),
                    errorText = if (state.showAreaError) {
                        stringResource(Res.string.add_land_surface_error)
                    } else {
                        null
                    },
                    keyboardType = KeyboardType.Decimal,
                )

                ManijeroMeasureField(
                    value = state.treeCountText,
                    onValueChange = { handleAction(AddLandAction.TreeCountChanged(it)) },
                    label = stringResource(Res.string.add_land_trees_label),
                    modifier = Modifier.focusRequester(treeCountFocus),
                    supportingText = stringResource(Res.string.add_land_trees_help),
                    errorText = if (state.showTreeCountError) {
                        stringResource(Res.string.add_land_trees_error)
                    } else {
                        null
                    },
                    keyboardType = KeyboardType.Number,
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

/** The plain-Spanish label of one approved variety, shared by both forms and the land details. */
internal fun landVarietyLabel(variety: LandVariety): StringResource = when (variety) {
    LandVariety.UNKNOWN -> Res.string.add_land_unknown
    LandVariety.PICUAL -> Res.string.add_land_variety_picual
    LandVariety.HOJIBLANCA -> Res.string.add_land_variety_hojiblanca
    LandVariety.PICUDO -> Res.string.add_land_variety_picudo
    LandVariety.LECHIN_DE_SEVILLA -> Res.string.add_land_variety_lechin_de_sevilla
    LandVariety.ARBEQUINA -> Res.string.add_land_variety_arbequina
    LandVariety.MANZANILLA -> Res.string.add_land_variety_manzanilla
    LandVariety.GORDAL -> Res.string.add_land_variety_gordal
    LandVariety.MIXED -> Res.string.add_land_variety_mixed
    LandVariety.OTHER -> Res.string.add_land_variety_other
}

@Preview(name = "Add land — blank")
@Composable
private fun AddLandBlankPreview() {
    ManijeroTheme { AddLandScreen(state = AddLandState(), onAction = {}, onCancel = {}) }
}

@Preview(name = "Add land — missing name and zone errors")
@Composable
private fun AddLandRequiredErrorsPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(
                name = "",
                zone = "",
                showNameError = true,
                showZoneError = true,
            ),
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
                zone = "Camino de la Fuente",
                municipality = "Martos",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
                variety = LandVariety.PICUAL,
                areaText = "1,5",
                treeCountText = "85",
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Add land — custom variety")
@Composable
private fun AddLandCustomVarietyPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(
                name = "La Loma",
                zone = "Linde del arroyo",
                variety = LandVariety.OTHER,
                varietyOther = "Royal de Cazorla",
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Add land — measure errors")
@Composable
private fun AddLandMeasureErrorsPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(
                name = "La Loma",
                zone = "El Llano",
                variety = LandVariety.OTHER,
                areaText = "1,234",
                treeCountText = "0",
                showVarietyOtherError = true,
                showAreaError = true,
                showTreeCountError = true,
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
                zone = "El Llano",
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
                zone = "Paraje de la Fuente del Roble, junto al cortijo viejo",
                municipality = "Villanueva del Arzobispo (Sierra de Cazorla)",
                waterRegime = WaterRegime.MIXED,
                productionMethod = ProductionMethod.ORGANIC,
                variety = LandVariety.LECHIN_DE_SEVILLA,
                areaText = "12,75",
                treeCountText = "1200",
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
            state = AddLandState(name = "Los Olivos", zone = "El Llano"),
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
            state = AddLandState(
                name = "Los Olivos",
                zone = "Camino de la Fuente",
                municipality = "Martos",
            ),
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
                zone = "Camino de la Fuente",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Add land — narrow, large font, required errors", widthDp = 320, fontScale = 2f)
@Composable
private fun AddLandNarrowLargeFontRequiredErrorsPreview() {
    ManijeroTheme {
        AddLandScreen(
            state = AddLandState(
                municipality = "Úbeda",
                showNameError = true,
                showZoneError = true,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}
