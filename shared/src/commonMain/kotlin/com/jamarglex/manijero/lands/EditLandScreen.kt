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
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.semantics.LiveRegionMode
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
import manijero.shared.generated.resources.add_land_municipality_label
import manijero.shared.generated.resources.add_land_name_error
import manijero.shared.generated.resources.add_land_name_label
import manijero.shared.generated.resources.add_land_production_conventional
import manijero.shared.generated.resources.add_land_production_label
import manijero.shared.generated.resources.add_land_production_mixed
import manijero.shared.generated.resources.add_land_production_organic
import manijero.shared.generated.resources.add_land_surface_error
import manijero.shared.generated.resources.add_land_surface_help
import manijero.shared.generated.resources.add_land_surface_label
import manijero.shared.generated.resources.add_land_trees_error
import manijero.shared.generated.resources.add_land_trees_help
import manijero.shared.generated.resources.add_land_trees_label
import manijero.shared.generated.resources.add_land_unknown
import manijero.shared.generated.resources.add_land_variety_help
import manijero.shared.generated.resources.add_land_variety_label
import manijero.shared.generated.resources.add_land_variety_other_error
import manijero.shared.generated.resources.add_land_variety_other_help
import manijero.shared.generated.resources.add_land_variety_other_label
import manijero.shared.generated.resources.add_land_variety_other_too_long
import manijero.shared.generated.resources.add_land_water_dryland
import manijero.shared.generated.resources.add_land_water_irrigated
import manijero.shared.generated.resources.add_land_water_label
import manijero.shared.generated.resources.add_land_water_mixed
import manijero.shared.generated.resources.add_land_zone_error
import manijero.shared.generated.resources.add_land_zone_help
import manijero.shared.generated.resources.add_land_zone_label
import manijero.shared.generated.resources.add_land_zone_too_long
import manijero.shared.generated.resources.edit_land_description
import manijero.shared.generated.resources.edit_land_missing
import manijero.shared.generated.resources.edit_land_save
import manijero.shared.generated.resources.edit_land_save_failed
import manijero.shared.generated.resources.edit_land_title
import org.jetbrains.compose.resources.stringResource

/**
 * Short shared form to correct one land. It renders whatever [state] it receives and reports every
 * interaction through [onAction] or [onCancel]; persistence happens in the caller and only ever
 * targets [EditLandState.landId].
 *
 * The form is prefilled from the stored record. A legacy record loaded without a zone opens with an
 * empty required zone field and cannot be saved until one is written. Saving with any invalid field
 * writes nothing and moves focus to the first invalid one, in layout order.
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
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Column(
                modifier = Modifier
                    .widthIn(max = 720.dp)
                    .fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(
                    text = stringResource(Res.string.edit_land_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                    // The form title is the one heading semantic on this surface.
                    modifier = Modifier.semantics { heading() },
                )
                Text(
                    text = stringResource(Res.string.edit_land_description),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                // Same recoverable first-invalid path as the add form: the focus is requested from the
                // save path, so a repeated invalid attempt re-focuses the field.
                val nameFocus = remember { FocusRequester() }
                val zoneFocus = remember { FocusRequester() }
                val varietyOtherFocus = remember { FocusRequester() }
                val areaFocus = remember { FocusRequester() }
                val treeCountFocus = remember { FocusRequester() }
                val handleAction: (EditLandAction) -> Unit = { action ->
                    if (action is EditLandAction.SaveClicked) {
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
                    onValueChange = { handleAction(EditLandAction.NameChanged(it)) },
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
                    onValueChange = { handleAction(EditLandAction.ZoneChanged(it)) },
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
                    onValueChange = { onAction(EditLandAction.MunicipalityChanged(it)) },
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
                            handleAction(EditLandAction.VarietySelected(LAND_VARIETY_OPTIONS[index]))
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
                        onValueChange = { handleAction(EditLandAction.VarietyOtherChanged(it)) },
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
                    onValueChange = { handleAction(EditLandAction.AreaChanged(it)) },
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
                    onValueChange = { handleAction(EditLandAction.TreeCountChanged(it)) },
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
                        onClick = { handleAction(EditLandAction.SaveClicked) },
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

@Suppress("LongParameterList")
private fun previewEditLandState(
    name: String = "Los Olivos",
    zone: String = "Camino de la Fuente",
    municipality: String = "",
    waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    variety: LandVariety = LandVariety.UNKNOWN,
    varietyOther: String = "",
    areaText: String = "",
    treeCountText: String = "",
    preservedNotes: String? = null,
    showNameError: Boolean = false,
    showZoneError: Boolean = false,
    showVarietyOtherError: Boolean = false,
    showAreaError: Boolean = false,
    showTreeCountError: Boolean = false,
    failure: EditLandFailure? = null,
) = EditLandState(
    landId = "land-1",
    name = name,
    zone = zone,
    municipality = municipality,
    waterRegime = waterRegime,
    productionMethod = productionMethod,
    variety = variety,
    varietyOther = varietyOther,
    areaText = areaText,
    treeCountText = treeCountText,
    preservedNotes = preservedNotes,
    showNameError = showNameError,
    showZoneError = showZoneError,
    showVarietyOtherError = showVarietyOtherError,
    showAreaError = showAreaError,
    showTreeCountError = showTreeCountError,
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
                zone = "Linde del arroyo",
                municipality = "Martos",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
                variety = LandVariety.PICUAL,
                areaText = "2,5",
                treeCountText = "85",
                preservedNotes = "Junto al arroyo",
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — legacy land without zone")
@Composable
private fun EditLandLegacyWithoutZonePreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                name = "Los Olivos",
                zone = "",
                municipality = "Martos",
                showZoneError = true,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — missing name and zone errors")
@Composable
private fun EditLandRequiredErrorsPreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                name = "  ",
                zone = "   ",
                municipality = "Úbeda",
                showNameError = true,
                showZoneError = true,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — custom variety")
@Composable
private fun EditLandCustomVarietyPreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                name = "La Loma",
                variety = LandVariety.OTHER,
                varietyOther = "Royal de Cazorla",
            ),
            onAction = {},
            onCancel = {},
        )
    }
}

@Preview(name = "Edit land — measure errors")
@Composable
private fun EditLandMeasureErrorsPreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                variety = LandVariety.OTHER,
                varietyOther = "",
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

@Preview(name = "Edit land — write failure")
@Composable
private fun EditLandWriteFailurePreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                name = "La Loma",
                zone = "El Llano",
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

@Preview(name = "Edit land — narrow, large font, required errors", widthDp = 320, fontScale = 2f)
@Composable
private fun EditLandNarrowLargeFontRequiredErrorsPreview() {
    ManijeroTheme {
        EditLandScreen(
            state = previewEditLandState(
                name = "  ",
                zone = "",
                municipality = "Úbeda",
                showNameError = true,
                showZoneError = true,
            ),
            onAction = {},
            onCancel = {},
        )
    }
}
