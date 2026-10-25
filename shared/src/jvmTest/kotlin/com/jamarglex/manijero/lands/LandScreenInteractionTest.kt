package com.jamarglex.manijero.lands

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test
import kotlin.test.assertEquals

@OptIn(ExperimentalTestApi::class)
class LandScreenInteractionTest {
    @Test
    fun rowActionsNameAndSelectTheirLandWithoutChangingTheList() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            val first = Land("first", "Los Olivos", "El Llano", createdAtEpochMillis = 0, updatedAtEpochMillis = 0)
            val second = Land("second", "La Loma", "La Umbría", createdAtEpochMillis = 0, updatedAtEpochMillis = 0)
            val edits = mutableListOf<Land>()
            val removals = mutableListOf<Land>()
            setContent {
                ManijeroTheme(darkTheme = false) {
                    LandListScreen(
                        state = LandListState(lands = listOf(first, second)),
                        onAddLand = {}, onEditLand = edits::add, onRemoveLand = removals::add,
                        onRetry = {}, onQueryChange = {},
                    )
                }
            }
            onNodeWithContentDescription("Editar el terreno «La Loma»").performClick()
            onNodeWithContentDescription("Eliminar el terreno «Los Olivos»").performClick()
            assertEquals(listOf(second), edits)
            assertEquals(listOf(first), removals)
        }

    @Test
    fun removeConfirmationDeletesOnlyAfterExplicitConfirmation() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            var removed = 0
            var cancelled = 0
            setContent {
                ManijeroTheme(darkTheme = false) {
                    RemoveLandScreen(
                        state = RemoveLandState(
                            landId = "land-1", name = "La Loma", zone = "El Llano",
                            municipality = null, waterRegime = WaterRegime.UNKNOWN,
                            productionMethod = ProductionMethod.UNKNOWN, variety = LandVariety.UNKNOWN,
                            varietyOther = null, areaHectares = null, treeCount = null,
                        ),
                        onRemove = { removed++ }, onCancel = { cancelled++ },
                    )
                }
            }
            assertEquals(0, removed)
            onNodeWithText("Cancelar").performClick()
            assertEquals(0, removed)
            assertEquals(1, cancelled)
            onNodeWithText("Eliminar el terreno").performClick()
            assertEquals(1, removed)
        }
}
