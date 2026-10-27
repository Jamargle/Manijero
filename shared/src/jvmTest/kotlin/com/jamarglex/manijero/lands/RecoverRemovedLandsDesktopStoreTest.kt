package com.jamarglex.manijero.lands

import java.nio.file.Files
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Desktop integration check for the recoverable lifecycle: the file-backed store the Desktop app
 * injects must keep a removed land across a restart, restore it, and delete it for good only through
 * the second confirmation's repository call. Synthetic fixtures only.
 */
class RecoverRemovedLandsDesktopStoreTest {
    @Test
    fun create_remove_restart_restore_and_permanently_delete_through_the_file() {
        val directory = Files.createTempDirectory("manijero-recover-lands")
        val path = directory.resolve("lands-v1.txt")
        try {
            val first = LandRepository(FileLandStorage(path)).create(
                LandDraft("Los Olivos", "El Llano"),
                now = 1,
            )
            val second = LandRepository(FileLandStorage(path)).create(
                LandDraft(
                    name = "La Loma",
                    zone = "Linde del arroyo",
                    municipality = "Martos",
                    waterRegime = WaterRegime.IRRIGATED,
                    productionMethod = ProductionMethod.ORGANIC,
                    areaHectares = 3.5,
                    treeCount = 120,
                ),
                now = 2,
            )

            assertEquals(
                LandLifecycleResult.Done(first),
                LandRepository(FileLandStorage(path)).moveToRemoved(first.id, now = 3),
            )

            val afterRemoval = LandRepository(FileLandStorage(path))
            assertEquals(listOf(second), afterRemoval.list())
            assertEquals(listOf(RemovedLand(first, 3)), afterRemoval.listRemoved())

            assertEquals(
                LandLifecycleResult.Done(first),
                LandRepository(FileLandStorage(path)).restore(first.id),
            )

            val afterRestore = LandRepository(FileLandStorage(path))
            assertEquals(listOf(second, first), afterRestore.list())
            assertEquals(emptyList(), afterRestore.listRemoved())

            assertEquals(
                LandLifecycleResult.Done(second),
                LandRepository(FileLandStorage(path)).moveToRemoved(second.id, now = 4),
            )
            assertEquals(
                LandLifecycleResult.Done(second),
                LandRepository(FileLandStorage(path)).permanentlyDelete(second.id),
            )

            val afterDeletion = LandRepository(FileLandStorage(path))
            assertEquals(listOf(first), afterDeletion.list())
            assertEquals(emptyList(), afterDeletion.listRemoved())
            assertTrue(
                directory.toFile().listFiles()?.map { it.name } == listOf("lands-v1.txt"),
                "no temporary file may survive a completed write",
            )
        } finally {
            deleteRecursively(directory)
        }
    }

    @Test
    fun a_v1_file_migrates_once_and_keeps_every_record_as_active() {
        val directory = Files.createTempDirectory("manijero-recover-lands-migration")
        val path = directory.resolve("lands-v1.txt")
        try {
            Files.writeString(
                path,
                """
                land-store-v1
                land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
                land-2|La Loma|La Vega||IRRIGATED|MIXED|OTHER|Royal|2.5|1200|Nota|3|4
                """.trimIndent(),
            )

            val migrated = LandRepository(FileLandStorage(path)).list()

            assertEquals(listOf("land-1", "land-2"), migrated.map { it.id })
            val migratedFile = Files.readString(path)
            assertTrue(migratedFile.startsWith("land-store-v2\nactive\n"))
            assertTrue(migratedFile.endsWith("removed"), "the migrated aggregate has an empty removed list")

            val restarted = LandRepository(FileLandStorage(path))
            assertEquals(migrated, restarted.list())
            assertEquals(migratedFile, Files.readString(path), "the restart must not migrate again")
        } finally {
            deleteRecursively(directory)
        }
    }

    private fun deleteRecursively(directory: Path) {
        directory.toFile().listFiles()?.forEach { it.delete() }
        Files.deleteIfExists(directory)
    }
}
