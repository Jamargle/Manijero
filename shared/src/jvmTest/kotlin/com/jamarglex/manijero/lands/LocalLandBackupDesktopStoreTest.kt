package com.jamarglex.manijero.lands

import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Desktop integration check for the same-device automatic copies: the file-backed store keeps
 * bounded sibling copies, recovers a damaged land file on restart, and makes a permanent deletion
 * reach every copy. Synthetic fixtures in a temporary directory only.
 */
class LocalLandBackupDesktopStoreTest {
    @Test
    fun a_damaged_land_file_is_recovered_from_the_newest_valid_copy_on_restart() {
        val directory = Files.createTempDirectory("manijero-auto-backup-recovery")
        val path = directory.resolve(STORE_FILE)
        try {
            val first = repository(path).create(LandDraft("Los Olivos", "El Llano"), now = 1)
            val second = repository(path).create(LandDraft("La Loma", "La Vega"), now = 2)
            repository(path).create(LandDraft("El Cortijo", "Las Eras"), now = 3)
            // The newest copy is truncated and the primary land file is no longer a store at all.
            Files.writeString(snapshotPath(path, 1), "copia cortada")
            Files.writeString(path, "no es un almacén de terrenos")

            val reopened = repository(path)

            assertEquals(listOf(first, second), reopened.list())
            assertEquals(
                LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY,
                reopened.consumeRecovery(),
            )
            assertTrue(Files.readString(path).startsWith("land-store-v2\nactive\n"))
            val copiedIds = snapshotFiles(path).mapNotNull { file ->
                LandSnapshotFormat.unwrap(Files.readString(file))
            }
            assertEquals(2, copiedIds.size, "the damaged copy is dropped and the valid ones stay")
            assertTrue(copiedIds.all { snapshot -> snapshot.active.map { it.id } == listOf(first.id, second.id) })
            assertTrue(
                directory.toFile().listFiles()?.map { it.name }.orEmpty().none { it.endsWith(".tmp") },
                "no temporary file survives a completed write",
            )
        } finally {
            deleteRecursively(directory)
        }
    }

    @Test
    fun the_retained_copies_stay_bounded_and_follow_the_primary_store() {
        val directory = Files.createTempDirectory("manijero-auto-backup-retention")
        val path = directory.resolve(STORE_FILE)
        try {
            var next = 0
            val writer = LandRepository(
                storage = FileLandStorage(path),
                idGenerator = { "land-${next++}" },
            )
            repeat(8) { index ->
                writer.create(LandDraft("Finca $index", "El Llano"), now = index.toLong())
            }

            val copiedIds = snapshotFiles(path)
            assertEquals(MAX_AUTOMATIC_LAND_SNAPSHOTS, copiedIds.size)
            val newest = assertNotNull(LandSnapshotFormat.unwrap(Files.readString(copiedIds.first())))
            assertEquals(LandStoreFormat.decode(Files.readString(path)), newest)
            assertEquals(
                (0..7).map { "land-$it" },
                newest.active.map { it.id },
                "the newest copy is the whole aggregate the last write committed",
            )
            val older = copiedIds.drop(1).map { file ->
                assertNotNull(LandSnapshotFormat.unwrap(Files.readString(file)))
            }
            assertEquals(
                listOf(7, 6),
                older.map { it.active.size },
                "the older copies are the state before each of the last two changes",
            )

            val restarted = repository(path)
            assertEquals(newest, LandSnapshot(active = restarted.list()))
            assertNull(restarted.consumeRecovery(), "an intact store is not a recovery")
        } finally {
            deleteRecursively(directory)
        }
    }

    @Test
    fun a_permanent_deletion_purges_the_primary_file_and_every_copy() {
        val directory = Files.createTempDirectory("manijero-auto-backup-purge")
        val path = directory.resolve(STORE_FILE)
        try {
            val kept = repository(path).create(LandDraft("Los Olivos", "El Llano"), now = 1)
            val doomed = repository(path).create(LandDraft("La Loma", "La Vega"), now = 2)
            assertIs<LandLifecycleResult.Done>(repository(path).moveToRemoved(doomed.id, now = 3))

            assertIs<LandLifecycleResult.Done>(repository(path).permanentlyDelete(doomed.id))

            assertEquals(listOf(kept), repository(path).list())
            val copies = snapshotFiles(path).map { file ->
                assertNotNull(LandSnapshotFormat.unwrap(Files.readString(file)))
            }
            assertTrue(copies.isNotEmpty())
            assertTrue(copies.all { snapshot -> snapshot.removed.none { it.land.id == doomed.id } })
            assertTrue(copies.all { snapshot -> snapshot.active.none { it.id == doomed.id } })
            assertTrue(!Files.exists(purgeMarkerPath(path)), "the marker is cleared after a purge")
            assertEquals(
                listOf(kept),
                repository(path).list(),
                "a restart after the purge keeps only the kept land",
            )
        } finally {
            deleteRecursively(directory)
        }
    }

    private fun repository(path: Path): LandRepository = LandRepository(FileLandStorage(path))

    private fun snapshotPath(path: Path, slot: Int): Path =
        path.resolveSibling("${path.fileName}.snapshot-$slot")

    private fun purgeMarkerPath(path: Path): Path = path.resolveSibling("${path.fileName}.purge")

    private fun snapshotFiles(path: Path): List<Path> =
        (1..MAX_AUTOMATIC_LAND_SNAPSHOTS)
            .map { slot -> snapshotPath(path, slot) }
            .filter { Files.exists(it) }

    private fun deleteRecursively(directory: Path) {
        directory.toFile().listFiles()?.forEach { it.delete() }
        Files.deleteIfExists(directory)
    }

    private companion object {
        const val STORE_FILE = "lands-v1.txt"
    }
}
