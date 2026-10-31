package com.jamarglex.manijero.lands

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Export, preview, and replace-all restore through [LandBackupController] and
 * [LandRepository.replaceAll]: a valid file is previewed before anything is written, only the
 * explicit confirmation replaces both lists (after a pre-restore same-device copy), and an invalid
 * file or a refused write leaves the store and its copies untouched.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class LandBackupRestoreTest {
    @Test
    fun `export hands the whole aggregate to the picker and writes nothing locally`() = runTest {
        val storage = RecordingStore()
        val repository = LandRepository(storage, idGenerator = ids())
        val kept = repository.create(LandDraft("Los Olivos", "El Llano", notes = "Mi nota"), 1)
        val removed = repository.create(LandDraft("La Loma", "La Vega"), 2)
        repository.moveToRemoved(removed.id, now = 3)
        val writesBefore = storage.writes.toList()
        val files = FakeFiles()
        val controller = LandBackupController(repository, files, this)

        controller.export()
        advanceUntilIdle()

        assertEquals(LandBackupNotice.EXPORTED, controller.state.notice)
        assertEquals(LAND_BACKUP_SUGGESTED_FILE_NAME, files.savedName)
        assertEquals(
            LandBackupDecodeResult.Valid(
                LandSnapshot(active = listOf(kept), removed = listOf(RemovedLand(removed, 3))),
            ),
            LandBackupFormat.decode(assertNotNull(files.saved)),
        )
        assertEquals(writesBefore, storage.writes, "an export never writes the local store")
    }

    @Test
    fun `a cancelled or refused save is reported honestly`() = runTest {
        val repository = LandRepository(RecordingStore(), idGenerator = ids())
        val files = FakeFiles(saveResult = LandBackupSaveResult.Cancelled)
        val controller = LandBackupController(repository, files, this)

        controller.export()
        advanceUntilIdle()
        assertNull(controller.state.notice)
        assertFalse(controller.state.working)

        files.saveResult = LandBackupSaveResult.Failed
        controller.export()
        advanceUntilIdle()
        assertEquals(LandBackupNotice.EXPORT_FAILED, controller.state.notice)
    }

    @Test
    fun `a valid file is previewed and nothing is written until the person confirms`() = runTest {
        val storage = RecordingStore()
        val repository = LandRepository(storage, idGenerator = ids())
        val current = repository.create(LandDraft("Actual", "El Llano"), 1)
        val backup = backupSnapshot()
        val files = FakeFiles(openResult = LandBackupOpenResult.Opened(LandBackupFormat.encode(backup)))
        var restoredCallbacks = 0
        val controller = LandBackupController(repository, files, this, onRestored = { restoredCallbacks++ })
        val writesBefore = storage.writes.toList()

        controller.chooseFile()
        advanceUntilIdle()

        val preview = assertNotNull(controller.state.preview)
        assertEquals(backup, preview.backup)
        assertEquals(1, preview.currentActiveCount)
        assertEquals(0, preview.currentRemovedCount)
        assertEquals(writesBefore, storage.writes, "a preview writes nothing")
        assertEquals(listOf(current), repository.list())

        controller.confirmRestore()
        advanceUntilIdle()

        assertEquals(LandBackupNotice.RESTORED, controller.state.notice)
        assertNull(controller.state.preview)
        assertEquals(1, restoredCallbacks)
        assertEquals(backup, repository.snapshot(), "both lists are replaced exactly, nothing merged")
    }

    @Test
    fun `cancelling the preview keeps the current lands`() = runTest {
        val storage = RecordingStore()
        val repository = LandRepository(storage, idGenerator = ids())
        val current = repository.create(LandDraft("Actual", "El Llano"), 1)
        val files = FakeFiles(openResult = LandBackupOpenResult.Opened(LandBackupFormat.encode(backupSnapshot())))
        val controller = LandBackupController(repository, files, this)
        val writesBefore = storage.writes.toList()

        controller.chooseFile()
        advanceUntilIdle()
        controller.dismissPreview()
        controller.confirmRestore()
        advanceUntilIdle()

        assertEquals(LandBackupState(), controller.state)
        assertEquals(writesBefore, storage.writes)
        assertEquals(listOf(current), repository.list())
    }

    @Test
    fun `an invalid file changes neither the store nor its automatic copies`() = runTest {
        val valid = LandBackupFormat.encode(backupSnapshot())
        mapOf(
            LandBackupOpenResult.Opened("no es una copia") to LandBackupNotice.NOT_A_BACKUP,
            LandBackupOpenResult.Opened(valid.take(valid.length - 20)) to LandBackupNotice.DAMAGED,
            LandBackupOpenResult.Opened(
                LandBackupFormat.encodeFile(LandBackupFormat.portable(backupSnapshot()), version = 9),
            ) to LandBackupNotice.UNSUPPORTED_VERSION,
            LandBackupOpenResult.Opened(
                LandBackupFormat.encodeFile(
                    LandBackupFormat.portable(
                        LandSnapshot(active = listOf(backupLand("x", "Uno"), backupLand("x", "Dos"))),
                    ),
                ),
            ) to LandBackupNotice.INVALID_CONTENT,
            LandBackupOpenResult.TooLarge to LandBackupNotice.FILE_TOO_LARGE,
            LandBackupOpenResult.Failed to LandBackupNotice.OPEN_FAILED,
        ).forEach { (opened, expected) ->
            val storage = RecordingStore()
            val repository = LandRepository(storage, idGenerator = ids())
            repository.create(LandDraft("Actual", "El Llano"), 1)
            val primary = storage.value
            val copies = storage.snapshots.toList()
            val writes = storage.writes.toList()
            val controller = LandBackupController(repository, FakeFiles(openResult = opened), this)

            controller.chooseFile()
            advanceUntilIdle()

            assertEquals(expected, controller.state.notice, "$opened")
            assertNull(controller.state.preview)
            assertEquals(primary, storage.value)
            assertEquals(copies, storage.snapshots)
            assertEquals(writes, storage.writes, "no write of any kind after $expected")
        }
    }

    @Test
    fun `restore keeps a copy of the current lands before replacing them`() {
        val storage = RecordingStore()
        val repository = LandRepository(storage, idGenerator = ids())
        repository.create(LandDraft("Actual", "El Llano"), 1)
        val before = repository.snapshot()
        storage.writes.clear()

        assertEquals(LandReplaceResult.Replaced, repository.replaceAll(backupSnapshot()))

        assertEquals(listOf("snapshot", "primary", "snapshot"), storage.writes)
        assertEquals(backupSnapshot(), LandSnapshotFormat.unwrap(storage.snapshots[0]))
        assertEquals(before, LandSnapshotFormat.unwrap(storage.snapshots[1]), "the pre-restore state stays recoverable")
    }

    @Test
    fun `a refused pre-restore copy or primary write leaves the lands unchanged`() {
        listOf(
            RecordingStore().apply { refuseSnapshotWritesAfterSetup = true },
            RecordingStore().apply { refusePrimaryWritesAfterSetup = true },
        ).forEach { storage ->
            val repository = LandRepository(storage, idGenerator = ids())
            repository.create(LandDraft("Actual", "El Llano"), 1)
            val before = repository.snapshot()
            val primary = storage.value
            storage.armRefusals()

            assertEquals(LandReplaceResult.StorageFailed, repository.replaceAll(backupSnapshot()))

            assertEquals(primary, storage.value)
            assertEquals(before, repository.snapshot())
        }
    }

    @Test
    fun `an unreadable current store is never overwritten by a restore`() = runTest {
        val storage = RecordingStore()
        storage.value = "land-store-v2\nroto"
        val repository = LandRepository(storage, idGenerator = ids())
        val writes = storage.writes.toList()

        assertEquals(LandReplaceResult.CurrentUnreadable, repository.replaceAll(backupSnapshot()))
        assertEquals("land-store-v2\nroto", storage.value)
        assertEquals(writes, storage.writes)

        val controller = LandBackupController(
            repository,
            FakeFiles(openResult = LandBackupOpenResult.Opened(LandBackupFormat.encode(backupSnapshot()))),
            this,
        )
        controller.chooseFile()
        advanceUntilIdle()
        assertEquals(LandBackupNotice.STORE_UNREADABLE, controller.state.notice)
        assertNull(controller.state.preview)
    }

    @Test
    fun `an old file can bring back a land deleted for good, even with a pending purge marker`() {
        val storage = RecordingStore()
        val repository = LandRepository(storage, idGenerator = ids())
        val land = repository.create(LandDraft("Vieja", "El Llano"), 1)
        val oldFile = LandBackupFormat.encode(repository.snapshot())
        repository.moveToRemoved(land.id, now = 2)
        storage.refuseSnapshotRewrites = true
        repository.permanentlyDelete(land.id)
        assertNotNull(storage.purgeMarker, "the copies could not be sanitized, so the marker is pending")
        storage.refuseSnapshotRewrites = false

        val backup = (LandBackupFormat.decode(oldFile) as LandBackupDecodeResult.Valid).snapshot
        assertEquals(LandReplaceResult.Replaced, repository.replaceAll(backup))

        assertEquals(listOf(land), repository.list())
        assertNull(storage.purgeMarker)
    }

    @Test
    fun `a second tap while a picker is open is ignored`() = runTest {
        val repository = LandRepository(RecordingStore(), idGenerator = ids())
        val files = FakeFiles()
        val controller = LandBackupController(repository, files, this)

        controller.export()
        controller.export()
        controller.chooseFile()
        assertTrue(controller.state.working)
        advanceUntilIdle()

        assertEquals(1, files.saveCalls)
        assertEquals(0, files.openCalls)
    }

    private fun ids(): () -> String {
        var next = 0
        return { "local-${next++}" }
    }
}

private fun backupLand(id: String, name: String) = Land(
    id = id,
    name = name,
    zone = "Linde del arroyo",
    notes = "Nota del archivo",
    createdAtEpochMillis = 100,
    updatedAtEpochMillis = 200,
)

private fun backupSnapshot() = LandSnapshot(
    active = listOf(backupLand("b-1", "Del archivo"), backupLand("b-2", "Otra del archivo")),
    removed = listOf(RemovedLand(backupLand("b-3", "Eliminada del archivo"), 300)),
)

private class FakeFiles(
    var saveResult: LandBackupSaveResult = LandBackupSaveResult.Saved,
    var openResult: LandBackupOpenResult = LandBackupOpenResult.Cancelled,
) : LandBackupFiles {
    var saved: String? = null
    var savedName: String? = null
    var saveCalls = 0
    var openCalls = 0

    override suspend fun save(suggestedFileName: String, contents: String): LandBackupSaveResult {
        saveCalls++
        savedName = suggestedFileName
        if (saveResult == LandBackupSaveResult.Saved) saved = contents
        return saveResult
    }

    override suspend fun open(): LandBackupOpenResult {
        openCalls++
        return openResult
    }
}

private class RecordingStore : LandStorage, LandSnapshotStorage {
    var value: String? = null
    val snapshots = mutableListOf<String>()
    var purgeMarker: String? = null
    val writes = mutableListOf<String>()
    var refuseSnapshotRewrites = false
    var refuseSnapshotWritesAfterSetup = false
    var refusePrimaryWritesAfterSetup = false
    private var refusePrimary = false
    private var refuseSnapshots = false

    fun armRefusals() {
        refusePrimary = refusePrimaryWritesAfterSetup
        refuseSnapshots = refuseSnapshotWritesAfterSetup
    }

    override fun read(): String? = value

    override fun write(value: String) {
        if (refusePrimary) error("primary refused")
        writes += "primary"
        this.value = value
    }

    override fun readSnapshots(): List<String> = snapshots.toList()

    override fun writeSnapshot(value: String) {
        if (refuseSnapshots) error("copy refused")
        writes += "snapshot"
        snapshots.add(0, value)
        while (snapshots.size > MAX_AUTOMATIC_LAND_SNAPSHOTS) snapshots.removeAt(snapshots.lastIndex)
    }

    override fun replaceSnapshots(values: List<String>) {
        if (refuseSnapshotRewrites) error("copies refused")
        writes += "copies"
        snapshots.clear()
        snapshots.addAll(values.take(MAX_AUTOMATIC_LAND_SNAPSHOTS))
    }

    override fun readPurgeMarker(): String? = purgeMarker

    override fun writePurgeMarker(value: String?) {
        writes += "marker"
        purgeMarker = value
    }
}
