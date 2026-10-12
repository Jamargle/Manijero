package com.jamarglex.manijero.lands

/**
 * Pure form state for the "Añadir terreno" flow.
 *
 * It keeps the raw text the person typed so nothing is lost while correcting a mistake. Text is
 * trimmed only when validating and building a [LandDraft]; ids, timestamps, and the stored format
 * stay in [LandRepository]. No Compose or platform types belong here.
 */
data class AddLandState(
    val name: String = "",
    val municipality: String = "",
    val waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    val productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    val showNameError: Boolean = false,
    val showSaveError: Boolean = false,
) {
    val hasName: Boolean
        get() = name.isNotBlank()
}

sealed interface AddLandAction {
    data class NameChanged(val value: String) : AddLandAction
    data class MunicipalityChanged(val value: String) : AddLandAction
    data class WaterRegimeSelected(val value: WaterRegime) : AddLandAction
    data class ProductionMethodSelected(val value: ProductionMethod) : AddLandAction
    data object SaveClicked : AddLandAction
    data object SaveFailed : AddLandAction
}

fun AddLandState.reduce(action: AddLandAction): AddLandState = when (action) {
    is AddLandAction.NameChanged -> copy(
        name = action.value,
        showNameError = false,
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
    AddLandAction.SaveClicked -> copy(showNameError = !hasName, showSaveError = false)
    AddLandAction.SaveFailed -> copy(showSaveError = true)
}

/**
 * Maps the current form to the draft to persist, or returns `null` when the form must not be saved
 * yet. Areas and notes stay out of this short first form on purpose.
 */
fun AddLandState.toDraftOrNull(): LandDraft? {
    val trimmedName = name.trim()
    if (trimmedName.isEmpty()) return null
    return LandDraft(
        name = trimmedName,
        municipality = municipality.ifBlank { null },
        waterRegime = waterRegime,
        productionMethod = productionMethod,
    )
}
