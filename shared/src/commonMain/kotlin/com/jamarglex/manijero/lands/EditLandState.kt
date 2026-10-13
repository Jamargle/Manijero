package com.jamarglex.manijero.lands

/** Why the update did not happen, so copy and tests can tell the two cases apart. */
enum class EditLandFailure { WRITE_FAILED, LAND_MISSING }

/**
 * Pure form state for the "Editar terreno" flow.
 *
 * It is prefilled from one loaded [Land] and may write exactly that record: [landId] is the only
 * id it ever carries. Like the add form it keeps the raw text the person typed so nothing is lost
 * while correcting a mistake and trims only when validating and building a [LandDraft].
 * [preservedAreaHectares] and [preservedNotes] are carried through unchanged because this short
 * form neither collects nor shows them; dropping them would silently erase stored data. Ids,
 * timestamps, and persistence rules stay in [LandRepository]. No Compose or platform types belong
 * here.
 */
data class EditLandState(
    val landId: String,
    val name: String,
    val municipality: String,
    val waterRegime: WaterRegime,
    val productionMethod: ProductionMethod,
    val preservedAreaHectares: Double?,
    val preservedNotes: String?,
    val showNameError: Boolean = false,
    val failure: EditLandFailure? = null,
) {
    val hasName: Boolean
        get() = name.isNotBlank()
}

/**
 * The starting form for this loaded record: the stored name, the municipality as text (absent
 * municipality becomes an empty field), the two attributes exactly as stored (an `UNKNOWN` value
 * preselects `No lo sé`), and the two attributes this form does not collect carried along for the
 * update. Nothing is renamed, defaulted, or guessed.
 */
fun Land.toEditLandState(): EditLandState = EditLandState(
    landId = id,
    name = name,
    municipality = municipality.orEmpty(),
    waterRegime = waterRegime,
    productionMethod = productionMethod,
    preservedAreaHectares = areaHectares,
    preservedNotes = notes,
)

sealed interface EditLandAction {
    data class NameChanged(val value: String) : EditLandAction
    data class MunicipalityChanged(val value: String) : EditLandAction
    data class WaterRegimeSelected(val value: WaterRegime) : EditLandAction
    data class ProductionMethodSelected(val value: ProductionMethod) : EditLandAction
    data object SaveClicked : EditLandAction
    data class SaveFailed(val failure: EditLandFailure) : EditLandAction
}

fun EditLandState.reduce(action: EditLandAction): EditLandState = when (action) {
    is EditLandAction.NameChanged -> copy(
        name = action.value,
        showNameError = false,
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
    EditLandAction.SaveClicked -> copy(showNameError = !hasName, failure = null)
    is EditLandAction.SaveFailed -> copy(failure = action.failure)
}

/**
 * The draft to update with, or `null` when the form must not be written yet (blank name).
 *
 * An emptied municipality becomes absent (`null`), while the carried-through area and notes keep
 * whatever the stored record had, so a correction never deletes a value this form cannot show.
 */
fun EditLandState.toDraftOrNull(): LandDraft? {
    val trimmedName = name.trim()
    if (trimmedName.isEmpty()) return null
    return LandDraft(
        name = trimmedName,
        municipality = municipality.trim().ifEmpty { null },
        waterRegime = waterRegime,
        productionMethod = productionMethod,
        areaHectares = preservedAreaHectares,
        notes = preservedNotes,
    )
}
