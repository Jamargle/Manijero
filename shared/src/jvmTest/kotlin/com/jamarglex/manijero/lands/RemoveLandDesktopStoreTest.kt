package com.jamarglex.manijero.lands

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Desktop integration check for the composition root: the same file-backed store the Desktop app
 * injects must move exactly one land to the removed list and keep the other record after the app is
 * reopened.
 */
class RemoveLandDesktopStoreTest {
    @Test
    fun removing_one_land_survives_reopening_and_leaves_the_other_unchanged() {
        val directory = Files.createTempDirectory("manijero-remove-land")
        val path = directory.resolve("lands-v1.txt")
        try {
            val writer = LandRepository(FileLandStorage(path))
            val removed = writer.create(LandDraft("Los Olivos", "El Llano"), now = 1)
            val kept = writer.create(
                LandDraft(
                    name = "La Loma",
                    zone = "Linde del arroyo",
                    municipality = "Martos",
                    waterRegime = WaterRegime.IRRIGATED,
                    productionMethod = ProductionMethod.ORGANIC,
                    areaHectares = 3.5,
                    notes = "Junto al arroyo",
                ),
                now = 2,
            )

            val removedId = removed.toRemoveLandState().landId
            assertEquals(
                LandLifecycleResult.Done(removed),
                LandRepository(FileLandStorage(path)).moveToRemoved(removedId, now = 3),
            )

            assertTrue(Files.readString(path).startsWith("land-store-v2\nactive\n"))
            assertTrue(
                directory.toFile().listFiles()?.map { it.name }.orEmpty().none { it.endsWith(".tmp") },
                "an atomic write must leave no temporary file behind",
            )

            val reopened = LandRepository(FileLandStorage(path))
            assertEquals(listOf(kept), reopened.list(), "the other land must keep every stored value")
            assertFalse(
                reopened.list().any { it.id == removedId },
                "the removed record must leave the active list",
            )
            assertEquals(
                listOf(RemovedLand(removed, 3)),
                reopened.listRemoved(),
                "the removed record stays recoverable with every stored value",
            )
        } finally {
            directory.toFile().listFiles()?.forEach { it.delete() }
            Files.deleteIfExists(directory)
        }
    }

    @Test
    fun removing_the_last_land_leaves_a_reopenable_empty_active_store() {
        val directory = Files.createTempDirectory("manijero-remove-land-empty")
        val path = directory.resolve("lands-v1.txt")
        try {
            val writer = LandRepository(FileLandStorage(path))
            val only = writer.create(LandDraft("Los Olivos", "El Llano"), now = 1)

            LandRepository(FileLandStorage(path)).moveToRemoved(only.id, now = 2)

            val reopened = LandRepository(FileLandStorage(path))
            assertEquals(emptyList(), reopened.list())
            assertEquals(listOf(only), reopened.listRemoved().map { it.land })
        } finally {
            directory.toFile().listFiles()?.forEach { it.delete() }
            Files.deleteIfExists(directory)
        }
    }
}
