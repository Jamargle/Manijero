package com.jamarglex.manijero.lands

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Desktop integration check for the composition root: the same file-backed store the Desktop app
 * injects must keep the lands saved from the add-land form after the app is reopened.
 */
class AddLandDesktopStoreTest {
    @Test
    fun two_lands_saved_from_the_form_survive_reopening_the_desktop_store() {
        val directory = Files.createTempDirectory("manijero-add-land")
        val path = directory.resolve("lands-v1.txt")
        try {
            val nameOnly = AddLandState(name = "  Los Olivos  ", zone = "  El Llano  ")
                .reduce(AddLandAction.SaveClicked)
                .toDraftOrNull()!!
            val known = AddLandState(
                name = "La Loma",
                zone = "Linde del arroyo",
                municipality = "Martos",
            )
                .reduce(AddLandAction.WaterRegimeSelected(WaterRegime.IRRIGATED))
                .reduce(AddLandAction.ProductionMethodSelected(ProductionMethod.ORGANIC))
                .reduce(AddLandAction.SaveClicked)
                .toDraftOrNull()!!

            LandRepository(FileLandStorage(path)).create(nameOnly, now = 1)
            LandRepository(FileLandStorage(path)).create(known, now = 2)

            val reopened = LandRepository(FileLandStorage(path)).list()
            assertEquals(listOf("Los Olivos", "La Loma"), reopened.map { it.name })
            assertEquals(listOf("El Llano", "Linde del arroyo"), reopened.map { it.zone })
            assertEquals(WaterRegime.UNKNOWN, reopened[0].waterRegime)
            assertEquals(ProductionMethod.UNKNOWN, reopened[0].productionMethod)
            assertEquals(WaterRegime.IRRIGATED, reopened[1].waterRegime)
            assertEquals(ProductionMethod.ORGANIC, reopened[1].productionMethod)
            assertEquals("Martos", reopened[1].municipality)
        } finally {
            directory.toFile().listFiles()?.forEach { it.delete() }
            Files.deleteIfExists(directory)
        }
    }
}
