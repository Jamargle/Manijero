package com.jamarglex.manijero.lands

/**
 * Pure form state for the "Añadir terreno" flow.
 *
 * It keeps the raw text the person typed in every field so nothing is lost while correcting a
 * mistake. Text is normalised only through [LandFields] and when building a [LandDraft]; ids,
 * timestamps, and the stored format stay in [LandRepository]. No Compose or platform types belong
 * here.
 *
 * The zone is required, so [toDraftOrNull] refuses a blank or over-long one. Variety, custom variety
 * text, surface and tree count are optional: leaving them blank is a valid "not provided", never a
 * zero or a guess.
 */
data class AddLandState(
    val name: String = "",
    val zone: String = "",
    val municipality: String = "",
    val waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    val productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    val variety: LandVariety = LandVariety.UNKNOWN,
    val varietyOther: String = "",
    val areaText: String = "",
    val treeCountText: String = "",
    val showNameError: Boolean = false,
    val showZoneError: Boolean = false,
    val showVarietyOtherError: Boolean = false,
    val showAreaError: Boolean = false,
    val showTreeCountError: Boolean = false,
    val showSaveError: Boolean = false,
) {
    val hasName: Boolean
        get() = name.isNotBlank()

    val zoneIssue: ZoneProblem?
        get() = zoneProblem(zone)

    val varietyOtherValid: Boolean
        get() = isValidVarietyOther(variety, varietyOther)

    val areaMeasure: MeasureResult<Double>
        get() = parseAreaHectares(areaText)

    val treeCountMeasure: MeasureResult<Int>
        get() = parseTreeCount(treeCountText)
}

sealed interface AddLandAction {
    data class NameChanged(val value: String) : AddLandAction
    data class ZoneChanged(val value: String) : AddLandAction
    data class MunicipalityChanged(val value: String) : AddLandAction
    data class WaterRegimeSelected(val value: WaterRegime) : AddLandAction
    data class ProductionMethodSelected(val value: ProductionMethod) : AddLandAction
    data class VarietySelected(val value: LandVariety) : AddLandAction
    data class VarietyOtherChanged(val value: String) : AddLandAction
    data class AreaChanged(val value: String) : AddLandAction
    data class TreeCountChanged(val value: String) : AddLandAction
    data object SaveClicked : AddLandAction
    data object SaveFailed : AddLandAction
}

fun AddLandState.reduce(action: AddLandAction): AddLandState = when (action) {
    is AddLandAction.NameChanged -> copy(
        name = action.value,
        showNameError = false,
        showSaveError = false,
    )
    is AddLandAction.ZoneChanged -> copy(
        zone = action.value,
        showZoneError = false,
        showSaveError = false,
    )
    is AddLandAction.MunicipalityChanged -> copy(
        municipality = action.value,
        showSaveError = false,
    )
    is AddLandAction.WaterRegimeSelected -> copy(
        waterRegime = action.value,
        showSaveError = false,
    )
    is AddLandAction.ProductionMethodSelected -> copy(
        productionMethod = action.value,
        showSaveError = false,
    )
    is AddLandAction.VarietySelected -> copy(
        variety = action.value,
        showVarietyOtherError = false,
        showSaveError = false,
    )
    is AddLandAction.VarietyOtherChanged -> copy(
        varietyOther = action.value,
        showVarietyOtherError = false,
        showSaveError = false,
    )
    is AddLandAction.AreaChanged -> copy(
        areaText = action.value,
        showAreaError = false,
        showSaveError = false,
    )
    is AddLandAction.TreeCountChanged -> copy(
        treeCountText = action.value,
        showTreeCountError = false,
        showSaveError = false,
    )
    AddLandAction.SaveClicked -> copy(
        showNameError = !hasName,
        showZoneError = zoneIssue != null,
        showVarietyOtherError = !varietyOtherValid,
        showAreaError = !areaMeasure.isValid,
        showTreeCountError = !treeCountMeasure.isValid,
        showSaveError = false,
    )
    AddLandAction.SaveFailed -> copy(showSaveError = true)
}

/**
 * Maps the current form to the draft to persist, or returns `null` when the form must not be saved
 * yet. A rejected field keeps its raw text on screen; no value is trimmed into the draft from an
 * invalid input.
 */
fun AddLandState.toDraftOrNull(): LandDraft? {
    val trimmedName = name.trim()
    if (trimmedName.isEmpty()) return null
    if (zoneIssue != null) return null
    if (!varietyOtherValid) return null
    if (!areaMeasure.isValid) return null
    if (!treeCountMeasure.isValid) return null
    val area = areaMeasure.valueOrNull()
    val treeCount = treeCountMeasure.valueOrNull()
    return LandDraft(
        name = trimmedName,
        zone = zone.trim(),
        municipality = municipality.trim().ifEmpty { null },
        waterRegime = waterRegime,
        productionMethod = productionMethod,
        variety = variety,
        varietyOther = normalizedVarietyOther(variety, varietyOther),
        areaHectares = area,
        treeCount = treeCount,
    )
}
