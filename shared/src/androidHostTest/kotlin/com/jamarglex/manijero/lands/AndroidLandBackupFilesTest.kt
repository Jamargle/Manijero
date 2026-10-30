package com.jamarglex.manijero.lands

import android.net.Uri
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * The Android picker adapter maps a document-picker result to file work. Scripted launchers stand in
 * for the system picker and in-memory documents for the provider, so no real user file is used;
 * Robolectric supplies `Uri` on the host JVM.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class AndroidLandBackupFilesTest {
    private val documentUri: Uri = Uri.parse("content://com.example.documents/document/copia")

    @Test
    fun save_writes_the_backup_to_the_document_the_person_created() = runTest {
        val documents = MemoryDocuments()
        val launched = mutableListOf<String>()
        lateinit var files: AndroidLandBackupFiles
        files = AndroidLandBackupFiles(
            documents = documents,
            launchCreateDocument = { name -> launched += name; files.onCreateDocumentResult(documentUri) },
            launchOpenDocument = {},
            ioDispatcher = Dispatchers.Unconfined,
        )
        val contents = LandBackupFormat.encode(LandSnapshot(active = listOf(sampleLand())))

        assertEquals(LandBackupSaveResult.Saved, files.save(LAND_BACKUP_SUGGESTED_FILE_NAME, contents))

        assertEquals(listOf(LAND_BACKUP_SUGGESTED_FILE_NAME), launched)
        assertEquals(contents, documents.written[documentUri]?.toByteArray()?.decodeToString())
    }

    @Test
    fun a_cancelled_picker_writes_and_reads_nothing() = runTest {
        val documents = MemoryDocuments()
        lateinit var files: AndroidLandBackupFiles
        files = AndroidLandBackupFiles(
            documents = documents,
            launchCreateDocument = { files.onCreateDocumentResult(null) },
            launchOpenDocument = { files.onOpenDocumentResult(null) },
            ioDispatcher = Dispatchers.Unconfined,
        )

        assertEquals(LandBackupSaveResult.Cancelled, files.save("x.json", "{}"))
        assertEquals(LandBackupOpenResult.Cancelled, files.open())
        assertEquals(0, documents.opened)
    }

    @Test
    fun open_reads_the_chosen_document_and_it_validates_as_a_backup() = runTest {
        val snapshot = LandSnapshot(
            active = listOf(sampleLand()),
            removed = listOf(RemovedLand(sampleLand().copy(id = "land-2", name = "La Loma"), 9)),
        )
        val documents = MemoryDocuments(input = LandBackupFormat.encode(snapshot).encodeToByteArray())
        val files = openingFiles(documents)

        val opened = assertIs<LandBackupOpenResult.Opened>(files.open())
        assertEquals(LandBackupDecodeResult.Valid(snapshot), LandBackupFormat.decode(opened.text))
    }

    @Test
    fun open_maps_oversized_unreadable_and_non_text_documents() = runTest {
        assertEquals(
            LandBackupOpenResult.TooLarge,
            openingFiles(MemoryDocuments(input = ByteArray(MAX_LAND_BACKUP_BYTES + 10) { 32 })).open(),
        )
        assertEquals(LandBackupOpenResult.Failed, openingFiles(MemoryDocuments(input = null)).open())
        assertEquals(LandBackupOpenResult.Failed, openingFiles(MemoryDocuments(failReads = true)).open())
        assertEquals(
            LandBackupOpenResult.Failed,
            openingFiles(MemoryDocuments(input = byteArrayOf(0xFF.toByte(), 0xD8.toByte()))).open(),
        )
    }

    @Test
    fun a_missing_document_provider_is_a_failure_not_a_crash() = runTest {
        val files = AndroidLandBackupFiles(
            documents = MemoryDocuments(),
            launchCreateDocument = { throw android.content.ActivityNotFoundException() },
            launchOpenDocument = { throw android.content.ActivityNotFoundException() },
            ioDispatcher = Dispatchers.Unconfined,
        )
        assertEquals(LandBackupSaveResult.Failed, files.save("x.json", "{}"))
        assertEquals(LandBackupOpenResult.Failed, files.open())
    }

    @Test
    fun a_late_result_without_a_pending_request_is_ignored() = runTest {
        val documents = MemoryDocuments()
        lateinit var files: AndroidLandBackupFiles
        files = AndroidLandBackupFiles(
            documents = documents,
            launchCreateDocument = { files.onCreateDocumentResult(null) },
            launchOpenDocument = {},
            ioDispatcher = Dispatchers.Unconfined,
        )
        // A result delivered after its request was dropped (for example after recreation).
        files.onCreateDocumentResult(documentUri)
        files.onOpenDocumentResult(documentUri)

        assertEquals(LandBackupSaveResult.Cancelled, files.save("x.json", "{}"))
        assertEquals(0, documents.opened, "the stale document is never written")
    }

    private fun openingFiles(documents: MemoryDocuments): AndroidLandBackupFiles {
        lateinit var files: AndroidLandBackupFiles
        files = AndroidLandBackupFiles(
            documents = documents,
            launchCreateDocument = {},
            launchOpenDocument = { files.onOpenDocumentResult(documentUri) },
            ioDispatcher = Dispatchers.Unconfined,
        )
        return files
    }

    private class MemoryDocuments(
        private val input: ByteArray? = ByteArray(0),
        private val failReads: Boolean = false,
    ) : AndroidBackupDocuments {
        val written = mutableMapOf<Uri, ByteArrayOutputStream>()
        var opened = 0

        override fun openInput(uri: Uri): InputStream? {
            opened++
            if (failReads) throw IOException("unreadable")
            return input?.let(::ByteArrayInputStream)
        }

        override fun openOutput(uri: Uri): OutputStream? {
            opened++
            return ByteArrayOutputStream().also { written[uri] = it }
        }
    }

    private fun sampleLand() = Land(
        id = "land-1",
        name = "Los Olivos",
        zone = "El Llano",
        municipality = "Úbeda",
        notes = "Nota",
        createdAtEpochMillis = 1,
        updatedAtEpochMillis = 2,
    )
}
