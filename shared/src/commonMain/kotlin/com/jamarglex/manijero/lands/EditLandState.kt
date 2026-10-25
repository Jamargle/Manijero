package com.jamarglex.manijero.lands

/** Why the update did not happen, so copy and tests can tell the two cases apart. */
enum class EditLandFailure { WRITE_FAILED, LAND_MISSING }

/**
 * Pure form state for the "Editar terreno" flow.
 *
 * It is prefilled from one loaded [Land] and may write exactly that record: [landId] is the only id
 * it ever carries. Like the add form it keeps the raw text the person typed so nothing is lost while
 * correcting a mistake and normalises only when validating and building a [LandDraft].
 *
 * The zone is required, so a land always opens with its stored zone and the form refuses a blank or
 * over-long one. [preservedNotes] stays because this form still does not expose notes, and dropping
 * them would silently erase stored data. Ids, timestamps, and storage rules stay in
 * [LandRepository].
 */
data class EditLandState(
    val landId: String,
    val name: String,
    val zone: String,
    val municipality: String,
    val waterRegime: WaterRegime,
    val productionMethod: ProductionMethod,
    val variety: LandVariety,
    val varietyOther: String,
    val areaText: String,
    val treeCountText: String,
    val preservedNotes: String?,
    val showNameError: Boolean = false,
    val showZoneError: Boolean = false,
    val showVarietyOtherError: Boolean = false,
    val showAreaError: Boolean = false,
    val showTreeCountError: Boolean = false,
    val failure: EditLandFailure? = null,
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

/**
 * The starting form for this loaded record: every stored value as editable text, the municipality and
 * custom variety text as text (absent becomes an empty field), the two attributes exactly as stored
 * (an `UNKNOWN` value preselects `No lo sé`), and the notes this form does not show carried along for
 * the update. Nothing is renamed, defaulted, or guessed.
 */
fun Land.toEditLandState(): EditLandState = EditLandState(
    landId = id,
    name = name,
    zone = zone,
    municipality = municipality.orEmpty(),
    waterRegime = waterRegime,
    productionMethod = productionMethod,
    variety = variety,
    varietyOther = varietyOther.orEmpty(),
    areaText = areaInputText(areaHectares),
    treeCountText = treeCount?.toString().orEmpty(),
    preservedNotes = notes,
)

sealed interface EditLandAction {
    data class NameChanged(val value: String) : EditLandAction
    data class ZoneChanged(val value: String) : EditLandAction
    data class MunicipalityChanged(val value: String) : EditLandAction
    data class WaterRegimeSelected(val value: WaterRegime) : EditLandAction
    data class ProductionMethodSelected(val value: ProductionMethod) : EditLandAction
    data class VarietySelected(val value: LandVariety) : EditLandAction
    data class VarietyOtherChanged(val value: String) : EditLandAction
    data class AreaChanged(val value: String) : EditLandAction
    data class TreeCountChanged(val value: String) : EditLandAction
    data object SaveClicked : EditLandAction
    data class SaveFailed(val failure: EditLandFailure) : EditLandAction
}

fun EditLandState.reduce(action: EditLandAction): EditLandState = when (action) {
    is EditLandAction.NameChanged -> copy(
        name = action.value,
        showNameError = false,
        failure = null,
    )
    is EditLandAction.ZoneChanged -> copy(
        zone = action.value,
        showZoneError = false,
        failure = null,
    )
    is EditLandAction.MunicipalityChanged -> copy(
        municipality = action.value,
        failure = null,
    )
    is EditLandAction.WaterRegimeSelected -> copy(
        waterRegime = action.value,
        failure = null,
    )
    is EditLandAction.ProductionMethodSelected -> copy(
        productionMethod = action.value,
        failure = null,
    )
    is EditLandAction.VarietySelected -> copy(
        variety = action.value,
        showVarietyOtherError = false,
        failure = null,
    )
    is EditLandAction.VarietyOtherChanged -> copy(
        varietyOther = action.value,
        showVarietyOtherError = false,
        failure = null,
    )
    is EditLandAction.AreaChanged -> copy(
        areaText = action.value,
        showAreaError = false,
        failure = null,
    )
    is EditLandAction.TreeCountChanged -> copy(
        treeCountText = action.value,
        showTreeCountError = false,
        failure = null,
    )
    EditLandAction.SaveClicked -> copy(
        showNameError = !hasName,
        showZoneError = zoneIssue != null,
        showVarietyOtherError = !varietyOtherValid,
        showAreaError = !areaMeasure.isValid,
        showTreeCountError = !treeCountMeasure.isValid,
        failure = null,
    )
    is EditLandAction.SaveFailed -> copy(failure = action.failure)
}

/**
 * The draft to update with, or `null` when the form must not be written yet.
 *
 * Every collected field must be valid; an invalid one keeps its raw text on screen. An emptied
 * municipality becomes absent, while [preservedNotes] keeps whatever the stored record had, so a
 * correction never deletes a value this form cannot show.
 */
fun EditLandState.toDraftOrNull(): LandDraft? {
    val trimmedName = name.trim()
    if (trimmedName.isEmpty()) return null
    if (zoneIssue != null) return null
    if (!varietyOtherValid) return null
    if (!areaMeasure.isValid) return null
    if (!treeCountMeasure.isValid) return null
    return LandDraft(
        name = trimmedName,
        zone = zone.trim(),
        municipality = municipality.trim().ifEmpty { null },
        waterRegime = waterRegime,
        productionMethod = productionMethod,
        variety = variety,
        varietyOther = normalizedVarietyOther(variety, varietyOther),
        areaHectares = areaMeasure.valueOrNull(),
        treeCount = treeCountMeasure.valueOrNull(),
        notes = preservedNotes,
    )
}
