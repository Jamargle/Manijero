package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

/**
 * Integration between the edit form contract and the accepted [LandRepository.update] semantics:
 * exactly one record changes, untouched attributes survive, and an unknown id writes nothing.
 */
class EditLandRepositoryTest {
    @Test
    fun editing_one_land_leaves_the_other_record_and_its_encoded_line_untouched() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        val second = repository.create(
            LandDraft(
                name = "La Loma",
                zone = "Linde del arroyo",
                municipality = "Martos",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
                areaHectares = 3.5,
                notes = "Junto al arroyo",
            ),
            2,
        )
        val secondLineBefore = encodedLines(storage.value!!)[1]

        val updated = repository.update(
            first.id,
            LandDraft("Los Olivos corregido", "El Llano"),
            3,
        )

        assertNotNull(updated)
        val lands = repository.list()
        assertEquals(listOf(first.id, second.id), lands.map { it.id }, "creation order must hold")
        assertEquals(second, lands[1], "every field of the other land must be unchanged")
        assertEquals(
            secondLineBefore,
            encodedLines(storage.value!!)[1],
            "the other land's stored line must be byte-identical",
        )
        assertEquals(2, encodedLines(storage.value!!).size, "no second record may appear")
    }

    @Test
    fun the_edited_record_keeps_its_id_and_creation_time_and_takes_the_new_values() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        repository.create(LandDraft("La Loma", "La Vega"), 2)

        val updated = repository.update(
            first.id,
            LandDraft(
                name = "Los Olivos corregido",
                zone = "Camino de la Fuente",
                municipality = "Martos",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
            ),
            9,
        )

        assertEquals(first.id, updated?.id)
        assertEquals(first.createdAtEpochMillis, updated?.createdAtEpochMillis)
        assertEquals(9L, updated?.updatedAtEpochMillis)
        assertEquals("Los Olivos corregido", repository.list()[0].name)
        assertEquals(WaterRegime.IRRIGATED, repository.list()[0].waterRegime)
    }

    @Test
    fun an_edit_through_the_form_keeps_the_notes_it_never_collects() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val land = repository.create(
            LandDraft(
                name = "Los Olivos",
                zone = "El Llano",
                areaHectares = 2.5,
                notes = "Nota privada",
            ),
            1,
        )

        val draft = land.toEditLandState()
            .reduce(EditLandAction.NameChanged("  Los Olivos corregido  "))
            .toDraftOrNull()!!

        repository.update(land.id, draft, 2)

        val stored = repository(storage).list().single()
        assertEquals("Los Olivos corregido", stored.name)
        assertEquals(2.5, stored.areaHectares, "an edit must not erase the stored area")
        assertEquals("Nota privada", stored.notes, "an edit must not erase stored notes")
        assertEquals(land.id, stored.id)
        assertEquals(land.createdAtEpochMillis, stored.createdAtEpochMillis)
    }

    @Test
    fun a_legacy_land_without_zone_requires_a_zone_and_keeps_its_identity_notes_and_area() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val legacy = Land(
            id = "land-legacy",
            name = "Los Olivos",
            zone = null,
            municipality = "Martos",
            areaHectares = 2.5,
            notes = "Nota privada",
            createdAtEpochMillis = 1,
            updatedAtEpochMillis = 1,
        )
        storage.value =
            "land-store-v1\nland-legacy|Los Olivos|Martos|UNKNOWN|UNKNOWN|2.5|Nota privada|1|1"

        val prefilled = repository(storage).list().single().toEditLandState()
        assertEquals("", prefilled.zone)
        assertNull(prefilled.toDraftOrNull(), "a legacy record needs a zone before it can be saved")

        val draft = prefilled
            .reduce(EditLandAction.ZoneChanged("El Llano"))
            .toDraftOrNull()!!

        repository.update(legacy.id, draft, 5)

        val stored = repository(storage).list().single()
        assertEquals("land-legacy", stored.id)
        assertEquals(1L, stored.createdAtEpochMillis)
        assertEquals("El Llano", stored.zone)
        assertEquals(2.5, stored.areaHectares)
        assertEquals("Nota privada", stored.notes)
    }

    @Test
    fun a_name_only_land_edited_elsewhere_keeps_its_unknown_attributes() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val land = repository.create(LandDraft("Los Olivos", "El Llano"), 1)

        val draft = land.toEditLandState()
            .reduce(EditLandAction.MunicipalityChanged("Martos"))
            .toDraftOrNull()!!

        repository.update(land.id, draft, 2)

        val stored = repository(storage).list().single()
        assertEquals("Martos", stored.municipality)
        assertEquals(WaterRegime.UNKNOWN, stored.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, stored.productionMethod)
        assertEquals(LandVariety.UNKNOWN, stored.variety)
    }

    @Test
    fun an_edit_can_clear_optional_values_and_change_the_variety() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        val land = repository.create(
            LandDraft(
                name = "La Loma",
                zone = "El Llano",
                municipality = "Martos",
                waterRegime = WaterRegime.IRRIGATED,
                productionMethod = ProductionMethod.ORGANIC,
                variety = LandVariety.OTHER,
                varietyOther = "Royal de Cazorla",
                areaHectares = 2.5,
                treeCount = 85,
            ),
            1,
        )

        val draft = land.toEditLandState()
            .reduce(EditLandAction.MunicipalityChanged(""))
            .reduce(EditLandAction.WaterRegimeSelected(WaterRegime.UNKNOWN))
            .reduce(EditLandAction.ProductionMethodSelected(ProductionMethod.UNKNOWN))
            .reduce(EditLandAction.VarietySelected(LandVariety.PICUAL))
            .reduce(EditLandAction.AreaChanged(""))
            .reduce(EditLandAction.TreeCountChanged(""))
            .toDraftOrNull()!!

        repository.update(land.id, draft, 2)

        val reopened = repository(storage).list().single()
        assertNull(reopened.municipality, "a cleared municipality must be absent, not an empty text")
        assertEquals(WaterRegime.UNKNOWN, reopened.waterRegime)
        assertEquals(ProductionMethod.UNKNOWN, reopened.productionMethod)
        assertEquals(LandVariety.PICUAL, reopened.variety)
        assertNull(reopened.varietyOther)
        assertNull(reopened.areaHectares)
        assertNull(reopened.treeCount)
    }

    @Test
    fun updating_an_unknown_id_returns_null_and_writes_nothing() {
        val storage = MemoryStorage()
        val repository = repository(storage)
        repository.create(LandDraft("Los Olivos", "El Llano"), 1)
        val before = storage.value

        val result = repository.update("land-99", LandDraft("Fantasma", "El Llano"), 2)

        assertNull(result)
        assertEquals(before, storage.value, "a missing id must not rewrite the snapshot")
        assertEquals(listOf("Los Olivos"), repository.list().map { it.name })
    }

    private fun repository(storage: MemoryStorage): LandRepository =
        LandRepository(
            storage = storage,
            idGenerator = object : () -> String {
                private var next = 0

                override fun invoke(): String = "land-${next++}"
            },
        )

    private fun encodedLines(snapshot: String): List<String> =
        snapshot.lineSequence().drop(1).toList()

    private class MemoryStorage : LandStorage {
        var value: String? = null

        override fun read(): String? = value

        override fun write(value: String) {
            this.value = value
        }
    }
}
