package com.jamarglex.manijero.lands

import android.content.ContentResolver
import android.net.Uri
import java.io.InputStream
import java.io.OutputStream
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** The document streams behind a picked [Uri]; a seam so host tests never touch real user files. */
interface AndroidBackupDocuments {
    fun openInput(uri: Uri): InputStream?

    fun openOutput(uri: Uri): OutputStream?
}

/** The system document provider, opened through the app's [ContentResolver]. */
class ContentResolverBackupDocuments(private val resolver: ContentResolver) : AndroidBackupDocuments {
    override fun openInput(uri: Uri): InputStream? = resolver.openInputStream(uri)

    // "wt" truncates an existing document, so an overwritten backup never keeps a stale tail.
    override fun openOutput(uri: Uri): OutputStream? = resolver.openOutputStream(uri, "wt")
}

/**
 * Android [LandBackupFiles] on top of the Storage Access Framework (`ACTION_CREATE_DOCUMENT` and
 * `ACTION_OPEN_DOCUMENT`). The activity registers the two result launchers and forwards their
 * results to [onCreateDocumentResult] and [onOpenDocumentResult]; this class turns one launch plus
 * its result into one suspend call. No storage permission is needed and the app keeps no persistent
 * access to the chosen document.
 *
 * If the activity is recreated while the picker is open, the pending call is cancelled with its
 * composition and the late result is ignored: nothing is written to the store either way.
 */
class AndroidLandBackupFiles(
    private val documents: AndroidBackupDocuments,
    private val launchCreateDocument: (suggestedFileName: String) -> Unit,
    private val launchOpenDocument: () -> Unit,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : LandBackupFiles {
    private var pendingCreate: CompletableDeferred<Uri?>? = null
    private var pendingOpen: CompletableDeferred<Uri?>? = null

    /** The result of the create-document launcher: the chosen document, or `null` on cancel. */
    fun onCreateDocumentResult(uri: Uri?) {
        pendingCreate?.complete(uri)
        pendingCreate = null
    }

    /** The result of the open-document launcher: the chosen document, or `null` on cancel. */
    fun onOpenDocumentResult(uri: Uri?) {
        pendingOpen?.complete(uri)
        pendingOpen = null
    }

    override suspend fun save(suggestedFileName: String, contents: String): LandBackupSaveResult {
        if (pendingCreate != null) return LandBackupSaveResult.Failed
        val pending = CompletableDeferred<Uri?>().also { pendingCreate = it }
        val uri = try {
            launchCreateDocument(suggestedFileName)
            pending.await()
        } catch (cancellation: kotlinx.coroutines.CancellationException) {
            pendingCreate = null
            throw cancellation
        } catch (_: Exception) {
            // No document provider could handle the request (for example `ActivityNotFoundException`).
            pendingCreate = null
            return LandBackupSaveResult.Failed
        } ?: return LandBackupSaveResult.Cancelled
        return withContext(ioDispatcher) {
            runCatching {
                val output = documents.openOutput(uri) ?: error("No output stream")
                output.use { it.write(contents.encodeToByteArray()) }
            }.fold(onSuccess = { LandBackupSaveResult.Saved }, onFailure = { LandBackupSaveResult.Failed })
        }
    }

    override suspend fun open(): LandBackupOpenResult {
        if (pendingOpen != null) return LandBackupOpenResult.Failed
        val pending = CompletableDeferred<Uri?>().also { pendingOpen = it }
        val uri = try {
            launchOpenDocument()
            pending.await()
        } catch (cancellation: kotlinx.coroutines.CancellationException) {
            pendingOpen = null
            throw cancellation
        } catch (_: Exception) {
            pendingOpen = null
            return LandBackupOpenResult.Failed
        } ?: return LandBackupOpenResult.Cancelled
        return withContext(ioDispatcher) {
            runCatching {
                val input = documents.openInput(uri) ?: error("No input stream")
                input.use { it.readBoundedBackup() }
            }.fold(onSuccess = ::landBackupOpenResultFromBytes, onFailure = { LandBackupOpenResult.Failed })
        }
    }
}

/** Reads at most [MAX_LAND_BACKUP_BYTES] + 1 bytes (minSdk 29 has no `readNBytes`). */
private fun InputStream.readBoundedBackup(): ByteArray {
    val limit = MAX_LAND_BACKUP_BYTES + 1
    val output = java.io.ByteArrayOutputStream()
    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
    while (output.size() < limit) {
        val read = read(buffer, 0, minOf(buffer.size, limit - output.size()))
        if (read < 0) break
        output.write(buffer, 0, read)
    }
    return output.toByteArray()
}
