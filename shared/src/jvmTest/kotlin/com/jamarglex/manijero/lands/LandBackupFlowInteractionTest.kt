package com.jamarglex.manijero.lands

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import com.jamarglex.manijero.App
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * The whole backup flow in the real composition root on Desktop, with the real file-backed store and
 * a scripted picker: the warning is shown, a chosen file is previewed with counts and names, and only
 * `Sustituir todos mis terrenos` replaces both lists. Synthetic fixtures only.
 */
@OptIn(ExperimentalTestApi::class)
class LandBackupFlowInteractionTest {
    @Test
    fun previewThenConfirmReplacesBothListsAndExportSaysTheFileIsUnprotected() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            val directory = Files.createTempDirectory("manijero-backup-flow")
            try {
                val repository = LandRepository(FileLandStorage(directory.resolve("lands.txt")))
                repository.create(LandDraft("Mi finca actual", "El Llano"), now = 1)
                val backup = LandSnapshot(
                    active = listOf(
                        Land("b-1", "Olivar del archivo", "La Vega", notes = "Nota", createdAtEpochMillis = 1, updatedAtEpochMillis = 2),
                    ),
                    removed = listOf(
                        RemovedLand(Land("b-2", "Eliminada del archivo", "El Cerro", createdAtEpochMillis = 3, updatedAtEpochMillis = 4), 5),
                    ),
                )
                val files = ScriptedFiles(LandBackupOpenResult.Opened(LandBackupFormat.encode(backup)))
                setContent { App(landRepository = repository, landBackupFiles = files) }

                onNodeWithText("Copia en un archivo").performScrollTo().performClick()
                onNodeWithText("El archivo no está protegido").assertExists()

                onNodeWithText("Guardar copia en un archivo").performScrollTo().performClick()
                waitForIdle()
                onNodeWithText("Copia guardada", substring = true).assertExists()
                assertEquals(1, LandBackupFormat.decode(files.saved!!).let { (it as LandBackupDecodeResult.Valid).snapshot.active.size })

                onNodeWithText("Elegir un archivo").performScrollTo().performClick()
                waitForIdle()
                onNodeWithText("Esto es lo que contiene el archivo").assertExists()
                onNodeWithText("Terrenos: 1").assertExists()
                onNodeWithText("Olivar del archivo").assertExists()
                onNodeWithText("Terrenos eliminados: 1").assertExists()
                onNodeWithText("Eliminada del archivo").assertExists()
                onNodeWithText("hay 1 en Mis terrenos y 0 en Terrenos eliminados", substring = true).assertExists()
                assertEquals(listOf("Mi finca actual"), repository.list().map { it.name }, "a preview writes nothing")

                onNodeWithText("Sustituir todos mis terrenos").performScrollTo().performClick()
                waitForIdle()
                onNodeWithText("Tus terrenos se han recuperado desde el archivo.").assertExists()
                assertEquals(backup, repository.snapshot())
            } finally {
                directory.toFile().deleteRecursively()
            }
        }

    @Test
    fun aDamagedFileExplainsTheProblemAndKeepsTheLands() =
        runDesktopComposeUiTest(width = 900, height = 2400) {
            val directory = Files.createTempDirectory("manijero-backup-flow")
            try {
                val repository = LandRepository(FileLandStorage(directory.resolve("lands.txt")))
                repository.create(LandDraft("Mi finca actual", "El Llano"), now = 1)
                val before = repository.snapshot()
                val damaged = LandBackupFormat.encode(LandSnapshot()).dropLast(10)
                setContent {
                    App(landRepository = repository, landBackupFiles = ScriptedFiles(LandBackupOpenResult.Opened(damaged)))
                }

                onNodeWithText("Copia en un archivo").performScrollTo().performClick()
                onNodeWithText("Elegir un archivo").performScrollTo().performClick()
                waitForIdle()

                onNodeWithText("El archivo está incompleto, dañado o modificado. No se ha cambiado nada.").assertExists()
                onNodeWithText("Sustituir todos mis terrenos").assertDoesNotExist()
                assertEquals(before, repository.snapshot())
            } finally {
                directory.toFile().deleteRecursively()
            }
        }

    private class ScriptedFiles(private val openResult: LandBackupOpenResult) : LandBackupFiles {
        var saved: String? = null

        override suspend fun save(suggestedFileName: String, contents: String): LandBackupSaveResult {
            saved = contents
            return LandBackupSaveResult.Saved
        }

        override suspend fun open(): LandBackupOpenResult = openResult
    }
}
