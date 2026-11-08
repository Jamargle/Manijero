package com.jamarglex.manijero.inspector

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import com.jamarglex.manijero.screenshots.ScreenshotFixtures
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test
import kotlin.test.assertEquals

/** The read-only inspector: sections, `No se ejecutó` for stages that did not run, codes, `Volver`. */
@OptIn(ExperimentalTestApi::class)
class AnswerInspectorScreenTest {

    @Test
    fun showsTheNoteAndEverySectionAndLeavesTheTitleToTheTopBar() =
        runDesktopComposeUiTest(width = 900, height = 3000) {
            setContent {
                ManijeroTheme(darkTheme = false) {
                    AnswerInspectorScreen(inspection = ScreenshotFixtures.answeredInspection, onBack = {})
                }
            }

            // The title is the top bar's heading now, so the screen adds none of its own.
            onAllNodes(SemanticsMatcher.keyIsDefined(SemanticsProperties.Heading)).assertCountEquals(0)
            onNodeWithText("Inspección de la respuesta").assertDoesNotExist()
            onNodeWithText("Esta vista es solo para pruebas en este equipo. No se guarda ni se comparte.")
                .assertExists()
            listOf("Búsqueda", "Pasajes encontrados", "Redacción", "Comprobación", "Resultado").forEach {
                onNodeWithText(it).assertExists()
            }
            onNodeWithText("1. Solicitud única de la PAC").assertExists()
            onNodeWithText("Pasaje: pac-solicitud-unica-001").assertExists()
            onNodeWithText("Citado").assertExists()
            onNodeWithText("No citado").assertExists()
            onNodeWithText("Comprobación superada: sí").assertExists()
        }

    @Test
    fun stagesThatDidNotRunSayNoSeEjecutoAndCodesAreVerbatim() =
        runDesktopComposeUiTest(width = 900, height = 3000) {
            setContent {
                ManijeroTheme(darkTheme = false) {
                    AnswerInspectorScreen(inspection = ScreenshotFixtures.abstainedInspection, onBack = {})
                }
            }

            // The drafting stage did not run; the missing vector stage names itself.
            onAllNodesWithText("No se ejecutó").assertCountEquals(1)
            onNodeWithText("Búsqueda por significado: No se ejecutó").assertExists()
            onNodeWithText("No se encontró ningún pasaje.").assertExists()
            onNodeWithText("Comprobación superada: no").assertExists()
            onAllNodesWithText("Códigos: uncited_sentence").assertCountEquals(2)
            onNodeWithText("Motivo de la abstención: no_evidence").assertExists()
        }

    @Test
    fun volverReturnsThroughTheCallback() =
        runDesktopComposeUiTest(width = 900, height = 3000) {
            val backs = mutableListOf<Unit>()
            setContent {
                ManijeroTheme(darkTheme = false) {
                    AnswerInspectorScreen(
                        inspection = ScreenshotFixtures.answeredInspection,
                        onBack = { backs += Unit },
                    )
                }
            }

            onNodeWithText("Volver").performScrollTo().assertHasClickAction().performClick()

            assertEquals(1, backs.size)
        }
}
