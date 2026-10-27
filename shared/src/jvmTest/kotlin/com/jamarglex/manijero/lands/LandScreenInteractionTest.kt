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
            onNodeWithContentDescription("Quitar el terreno «Los Olivos»").performClick()
            assertEquals(listOf(second), edits)
            assertEquals(listOf(first), removals)
        }

    @Test
    fun theLandsListOnlyOpensTheRemovedListWhenItsCallbackIsWired() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            var opened = 0
            setContent {
                ManijeroTheme(darkTheme = false) {
                    LandListScreen(
                        state = LandListState(),
                        onAddLand = {}, onEditLand = {}, onRemoveLand = {},
                        onRetry = {}, onQueryChange = {},
                        onOpenRemovedLands = { opened++ },
                    )
                }
            }
            onNodeWithText("Terrenos eliminados").performClick()
            assertEquals(1, opened)
        }

    @Test
    fun theRecoveryNoticeExplainsTheRestoreAndIsDismissed() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            var dismissed = 0
            setContent {
                ManijeroTheme(darkTheme = false) {
                    LandListScreen(
                        state = LandListState(
                            lands = listOf(
                                Land(
                                    id = "first",
                                    name = "Los Olivos",
                                    zone = "El Llano",
                                    createdAtEpochMillis = 0,
                                    updatedAtEpochMillis = 0,
                                ),
                            ),
                        ),
                        onAddLand = {}, onEditLand = {}, onRemoveLand = {},
                        onRetry = {}, onQueryChange = {},
                        recovery = LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY,
                        onDismissRecovery = { dismissed++ },
                    )
                }
            }
            onNodeWithText("He recuperado tus terrenos").assertExists()
            onNodeWithText(
                "La copia principal no se podía leer. He usado la copia automática más reciente, " +
                    "guardada también en este dispositivo. Revisa que estén todos tus terrenos.",
            ).assertExists()
            assertEquals(0, dismissed)
            onNodeWithText("Entendido").performClick()
            assertEquals(1, dismissed)
        }

    @Test
    fun removeConfirmationMovesTheLandOnlyAfterExplicitConfirmation() =
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
            onNodeWithText("Quitar el terreno").performClick()
            assertEquals(1, removed)
        }

    @Test
    fun removedRowsRestoreOrOpenTheConfirmedDeletionForTheirOwnLand() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            val first = removed("first", "Los Olivos", "El Llano")
            val second = removed("second", "La Loma", "La Umbría")
            val restores = mutableListOf<RemovedLand>()
            val deletions = mutableListOf<RemovedLand>()
            setContent {
                ManijeroTheme(darkTheme = false) {
                    RemovedLandsScreen(
                        state = RemovedLandsState(lands = listOf(first, second)),
                        onBack = {},
                        onRestore = restores::add,
                        onDeletePermanently = deletions::add,
                        onRetry = {},
                    )
                }
            }
            assertEquals(0, restores.size)
            assertEquals(0, deletions.size)
            onNodeWithContentDescription("Restaurar el terreno «La Loma»").performClick()
            onNodeWithContentDescription("Borrar para siempre el terreno «Los Olivos»").performClick()
            assertEquals(listOf(second), restores)
            assertEquals(listOf(first), deletions)
        }

    @Test
    fun permanentDeletionDeletesOnlyAfterItsOwnConfirmation() =
        runDesktopComposeUiTest(width = 900, height = 1200) {
            var deleted = 0
            var cancelled = 0
            setContent {
                ManijeroTheme(darkTheme = false) {
                    PermanentlyDeleteLandScreen(
                        state = PermanentlyDeleteLandState(
                            landId = "land-1", name = "La Loma", zone = "El Llano",
                            municipality = null, waterRegime = WaterRegime.UNKNOWN,
                            productionMethod = ProductionMethod.UNKNOWN, variety = LandVariety.UNKNOWN,
                            varietyOther = null, areaHectares = null, treeCount = null,
                        ),
                        onDelete = { deleted++ }, onCancel = { cancelled++ },
                    )
                }
            }
            assertEquals(0, deleted)
            onNodeWithText("Cancelar").performClick()
            assertEquals(0, deleted)
            assertEquals(1, cancelled)
            onNodeWithText("Borrar para siempre el terreno").performClick()
            assertEquals(1, deleted)
        }

    private fun removed(id: String, name: String, zone: String): RemovedLand = RemovedLand(
        land = Land(
            id = id,
            name = name,
            zone = zone,
            createdAtEpochMillis = 0,
            updatedAtEpochMillis = 0,
        ),
        removedAtEpochMillis = 0,
    )
}
