package com.jamarglex.manijero.lands

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Desktop integration check for the composition root: the same file-backed store the Desktop app
 * injects must remove exactly one land and keep the other record after the app is reopened.
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
            assertTrue(LandRepository(FileLandStorage(path)).delete(removedId))

            val fileText = Files.readString(path)
            assertFalse(fileText.contains(removedId), "the removed record must leave the file")
            assertFalse(fileText.contains("Los Olivos"), "the removed name must leave the file")

            val reopened = LandRepository(FileLandStorage(path)).list()
            assertEquals(listOf(kept), reopened, "the other land must keep every stored value")
        } finally {
            Files.deleteIfExists(path)
            Files.deleteIfExists(directory)
        }
    }

    @Test
    fun removing_the_last_land_leaves_a_reopenable_empty_store() {
        val directory = Files.createTempDirectory("manijero-remove-land-empty")
        val path = directory.resolve("lands-v1.txt")
        try {
            val writer = LandRepository(FileLandStorage(path))
            val only = writer.create(LandDraft("Los Olivos", "El Llano"), now = 1)

            assertTrue(LandRepository(FileLandStorage(path)).delete(only.id))

            assertEquals(emptyList(), LandRepository(FileLandStorage(path)).list())
        } finally {
            Files.deleteIfExists(path)
            Files.deleteIfExists(directory)
        }
    }
}
