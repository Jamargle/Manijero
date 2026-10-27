package com.jamarglex.manijero.lands

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

/**
 * Desktop integration check for the composition root: the same file-backed store the Desktop app
 * injects must persist a correction to one land and leave the other record untouched after the app
 * is reopened.
 */
class EditLandDesktopStoreTest {
    @Test
    fun editing_one_land_survives_reopening_and_leaves_the_other_unchanged() {
        val directory = Files.createTempDirectory("manijero-edit-land")
        val path = directory.resolve("lands-v1.txt")
        try {
            val writer = LandRepository(FileLandStorage(path))
            val nameOnly = writer.create(LandDraft("Los Olivos", "El Llano"), now = 1)
            val known = writer.create(
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

            val draft = nameOnly.toEditLandState()
                .reduce(EditLandAction.NameChanged("  Los Olivos del camino  "))
                .toDraftOrNull()!!
            LandRepository(FileLandStorage(path)).update(nameOnly.id, draft, now = 3)

            val reopened = LandRepository(FileLandStorage(path)).list()
            assertEquals(listOf("Los Olivos del camino", "La Loma"), reopened.map { it.name })
            assertEquals(nameOnly.id, reopened[0].id)
            assertEquals(nameOnly.createdAtEpochMillis, reopened[0].createdAtEpochMillis)
            assertEquals("El Llano", reopened[0].zone)
            assertEquals(WaterRegime.UNKNOWN, reopened[0].waterRegime)
            assertEquals(ProductionMethod.UNKNOWN, reopened[0].productionMethod)
            assertEquals(known, reopened[1], "the other land must keep every stored value")
        } finally {
            directory.toFile().listFiles()?.forEach { it.delete() }
            Files.deleteIfExists(directory)
        }
    }

    @Test
    fun a_cleared_municipality_and_deliberate_unknown_survive_reopening() {
        val directory = Files.createTempDirectory("manijero-edit-land-unknown")
        val path = directory.resolve("lands-v1.txt")
        try {
            val writer = LandRepository(FileLandStorage(path))
            val land = writer.create(
                LandDraft(
                    name = "La Loma",
                    zone = "Linde del arroyo",
                    municipality = "Martos",
                    waterRegime = WaterRegime.IRRIGATED,
                    productionMethod = ProductionMethod.ORGANIC,
                ),
                now = 1,
            )

            val draft = land.toEditLandState()
                .reduce(EditLandAction.MunicipalityChanged(""))
                .reduce(EditLandAction.WaterRegimeSelected(WaterRegime.UNKNOWN))
                .reduce(EditLandAction.ProductionMethodSelected(ProductionMethod.UNKNOWN))
                .toDraftOrNull()!!
            LandRepository(FileLandStorage(path)).update(land.id, draft, now = 2)

            val reopened = LandRepository(FileLandStorage(path)).list().single()
            assertNull(reopened.municipality)
            assertEquals(WaterRegime.UNKNOWN, reopened.waterRegime)
            assertEquals(ProductionMethod.UNKNOWN, reopened.productionMethod)
        } finally {
            directory.toFile().listFiles()?.forEach { it.delete() }
            Files.deleteIfExists(directory)
        }
    }
}
