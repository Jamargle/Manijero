package com.jamarglex.manijero.lands

import java.nio.file.Files
import java.nio.file.Path
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import kotlin.io.path.createTempDirectory
import kotlin.io.path.readText
import kotlin.io.path.writeBytes
import kotlin.io.path.writeText
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * The Desktop picker adapter maps the native dialog's choice to file work: a temporary directory and
 * a scripted chooser stand in for the person, so no real user file and no window are involved.
 */
class DesktopLandBackupFilesTest {
    private val directory: Path = createTempDirectory("manijero-backup-test")

    @AfterTest
    fun cleanUp() {
        directory.toFile().deleteRecursively()
    }

    @Test
    fun `save writes the whole file where the person chose and adds the json extension`() = runTest {
        val chooser = ScriptedChooser(saveTarget = directory.resolve("mis-terrenos"))
        val files = DesktopLandBackupFiles(chooser, Dispatchers.Unconfined)

        val contents = LandBackupFormat.encode(LandSnapshot(active = listOf(sampleLand())))
        assertEquals(LandBackupSaveResult.Saved, files.save(LAND_BACKUP_SUGGESTED_FILE_NAME, contents))

        assertEquals(LAND_BACKUP_SUGGESTED_FILE_NAME, chooser.suggested)
        assertEquals(contents, directory.resolve("mis-terrenos.json").readText())
        assertEquals(listOf("mis-terrenos.json"), directory.toFile().list()!!.toList(), "no temporary file is left")
    }

    @Test
    fun `a cancelled save writes nothing and an unwritable place fails`() = runTest {
        val cancelled = DesktopLandBackupFiles(ScriptedChooser(saveTarget = null), Dispatchers.Unconfined)
        assertEquals(LandBackupSaveResult.Cancelled, cancelled.save("x.json", "{}"))
        assertTrue(directory.toFile().list()!!.isEmpty())

        val missingDirectory = directory.resolve("no-existe").resolve("copia.json")
        val failing = DesktopLandBackupFiles(ScriptedChooser(saveTarget = missingDirectory), Dispatchers.Unconfined)
        assertEquals(LandBackupSaveResult.Failed, failing.save("x.json", "{}"))
        assertFalse(Files.exists(missingDirectory))
    }

    @Test
    fun `open reads the chosen file, which then validates as a backup`() = runTest {
        val snapshot = LandSnapshot(active = listOf(sampleLand()))
        val source = directory.resolve("copia.json").also { it.writeText(LandBackupFormat.encode(snapshot)) }
        val files = DesktopLandBackupFiles(ScriptedChooser(openSource = source), Dispatchers.Unconfined)

        val opened = assertIs<LandBackupOpenResult.Opened>(files.open())
        assertEquals(LandBackupDecodeResult.Valid(snapshot), LandBackupFormat.decode(opened.text))
    }

    @Test
    fun `open maps cancel, a missing file, invalid text and an oversized file`() = runTest {
        assertEquals(
            LandBackupOpenResult.Cancelled,
            DesktopLandBackupFiles(ScriptedChooser(openSource = null), Dispatchers.Unconfined).open(),
        )
        assertEquals(
            LandBackupOpenResult.Failed,
            DesktopLandBackupFiles(ScriptedChooser(openSource = directory.resolve("nada.json")), Dispatchers.Unconfined).open(),
        )
        val binary = directory.resolve("foto.jpg").also { it.writeBytes(byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte())) }
        assertEquals(
            LandBackupOpenResult.Failed,
            DesktopLandBackupFiles(ScriptedChooser(openSource = binary), Dispatchers.Unconfined).open(),
        )
        val huge = directory.resolve("grande.json").also { it.writeBytes(ByteArray(MAX_LAND_BACKUP_BYTES + 10) { 32 }) }
        assertEquals(
            LandBackupOpenResult.TooLarge,
            DesktopLandBackupFiles(ScriptedChooser(openSource = huge), Dispatchers.Unconfined).open(),
        )
    }

    @Test
    fun `a dialog that throws is a failure, never a crash`() = runTest {
        val broken = object : DesktopBackupFileChooser {
            override fun chooseSaveTarget(suggestedFileName: String): Path = error("headless")
            override fun chooseOpenSource(): Path = error("headless")
        }
        val files = DesktopLandBackupFiles(broken, Dispatchers.Unconfined)
        assertEquals(LandBackupSaveResult.Failed, files.save("x.json", "{}"))
        assertEquals(LandBackupOpenResult.Failed, files.open())
    }

    private class ScriptedChooser(
        private val saveTarget: Path? = null,
        private val openSource: Path? = null,
    ) : DesktopBackupFileChooser {
        var suggested: String? = null

        override fun chooseSaveTarget(suggestedFileName: String): Path? {
            suggested = suggestedFileName
            return saveTarget
        }

        override fun chooseOpenSource(): Path? = openSource
    }

    private fun sampleLand() = Land(
        id = "land-1",
        name = "Los Olivos",
        zone = "El Llano",
        notes = "Nota",
        createdAtEpochMillis = 1,
        updatedAtEpochMillis = 2,
    )
}
