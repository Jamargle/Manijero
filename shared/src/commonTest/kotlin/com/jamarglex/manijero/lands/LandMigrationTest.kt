package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/**
 * The one-time `land-store-v1` migration: an already-shipped active-only snapshot becomes the current
 * aggregate exactly once, every decodable record stays active, and a refused write never replaces the
 * old store.
 */
class LandMigrationTest {
    @Test
    fun a_v1_store_migrates_every_decodable_record_as_active() {
        val storage = MemoryStorage(V1_SNAPSHOT)

        val lands = repository(storage).list()

        assertEquals(listOf("land-1", "land-3"), lands.map { it.id })
        assertEquals("Los Olivos", lands[0].name)
        assertEquals("El Llano", lands[0].zone)
        assertEquals(WaterRegime.DRYLAND, lands[0].waterRegime)
        assertEquals(1.5, lands[0].areaHectares)
        assertEquals(85, lands[0].treeCount)
        assertEquals("Royal", lands[1].varietyOther)
        assertEquals(2.5, lands[1].areaHectares)
        assertEquals("Nota", lands[1].notes)

        val stored = storage.value!!
        assertTrue(
            stored.startsWith("land-store-v2\nactive\n"),
            "the migrated store must be the current aggregate",
        )
        assertEquals(emptyList(), repository(storage).listRemoved())
        assertTrue(
            !stored.contains("Campos rotos"),
            "a malformed v1 record is skipped whole, never migrated",
        )
    }

    @Test
    fun the_migration_writes_once_and_a_restart_reads_it_without_migrating_again() {
        val storage = MemoryStorage(V1_SNAPSHOT)

        val first = repository(storage).list()
        assertEquals(1, storage.writes, "the first read performs exactly one migration write")
        val migrated = storage.value!!

        val restarted = repository(storage).list()

        assertEquals(first, restarted, "a restart must read the migrated lands unchanged")
        assertEquals(1, storage.writes, "the second read must not rewrite the store")
        assertEquals(migrated, storage.value)
    }

    @Test
    fun a_refused_migration_write_throws_and_keeps_the_v1_store() {
        val storage = FailingWriteStorage(V1_SNAPSHOT)

        assertFailsWith<IllegalStateException> { repository(storage).list() }

        assertEquals(V1_SNAPSHOT, storage.value, "the v1 records must survive an unwritable store")
    }

    @Test
    fun a_header_only_v1_store_migrates_to_an_empty_aggregate() {
        val storage = MemoryStorage("land-store-v1")

        assertEquals(emptyList(), repository(storage).list())

        assertEquals("land-store-v2\nactive\nremoved", storage.value)
        assertEquals(emptyList(), repository(storage).listRemoved())
    }

    @Test
    fun a_corrupt_v1_line_never_becomes_a_land() {
        val storage = MemoryStorage(
            """
            land-store-v1
            land-1|Sin zona||Martos|UNKNOWN|UNKNOWN|UNKNOWN|||||1|2
            land-2|Hora mala|El Llano||UNKNOWN|UNKNOWN|UNKNOWN|||||no|2
            land-3|Buena|La Vega||UNKNOWN|UNKNOWN|UNKNOWN|||||3|4
            """.trimIndent(),
        )

        assertEquals(listOf("land-3"), repository(storage).list().map { it.id })
    }

    private fun repository(storage: LandStorage): LandRepository = LandRepository(
        storage = storage,
        idGenerator = object : () -> String {
            private var next = 0

            override fun invoke(): String = "land-new-${next++}"
        },
    )

    private class MemoryStorage(initial: String? = null) : LandStorage {
        var value: String? = initial
        var writes: Int = 0

        override fun read(): String? = value

        override fun write(value: String) {
            writes++
            this.value = value
        }
    }

    private class FailingWriteStorage(var value: String?) : LandStorage {
        override fun read(): String? = value

        override fun write(value: String) {
            error("storage is read-only")
        }
    }

    private companion object {
        /** Synthetic fixtures only: no real person's land data is used here. */
        val V1_SNAPSHOT = """
            land-store-v1
            land-1|Los Olivos|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
            land-2|Campos rotos|El Llano||DRYLAND|ORGANIC|NO_EXISTE||1.5|85||3|4
            land-3|La Loma|La Vega||IRRIGATED|MIXED|OTHER|Royal|2.5|1200|Nota|5|6
        """.trimIndent()
    }
}
