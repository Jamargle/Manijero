package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * The same-device automatic copies: one bounded copy after each committed change, the newest fully
 * valid copy as the only recovery source, a failed read instead of a silent empty store, and a
 * permanent deletion that reaches every retained copy.
 */
class LandAutomaticBackupTest {
    @Test
    fun `every committed change rotates one bounded and complete copy`() {
        val storage = InMemoryLocalStore()
        val repository = repository(storage)

        val first = repository.create(LandDraft("Uno", "El Llano"), 1)
        assertCopyMatchesPrimary(storage)

        val second = repository.create(LandDraft("Dos", "La Vega"), 2)
        assertCopyMatchesPrimary(storage)

        repository.update(first.id, LandDraft("Uno corregido", "El Llano"), 3)
        assertCopyMatchesPrimary(storage)

        repository.moveToRemoved(second.id, now = 4)
        assertCopyMatchesPrimary(storage)

        repository.restore(second.id)
        assertCopyMatchesPrimary(storage)

        repository.moveToRemoved(second.id, now = 5)
        assertIs<LandLifecycleResult.Done>(repository.permanentlyDelete(second.id))
        assertCopyMatchesPrimary(storage)

        repeat(10) { index -> repository.create(LandDraft("Finca $index", "El Llano")) }
        assertEquals(MAX_AUTOMATIC_LAND_SNAPSHOTS, storage.snapshots.size)
        assertCopyMatchesPrimary(storage)
    }

    @Test
    fun `no copy is written when the primary write is refused`() {
        val storage = InMemoryLocalStore()
        val repository = repository(storage)
        val saved = repository.create(LandDraft("Uno", "El Llano"), 1)
        val primary = storage.value
        val copies = storage.snapshots.toList()
        storage.refusePrimaryWrites = true

        assertFailsWith<IllegalStateException> {
            repository.create(LandDraft("Dos", "La Vega"), 2)
        }

        assertEquals(primary, storage.value, "a refused write leaves the aggregate unchanged")
        assertEquals(copies, storage.snapshots, "a copy only follows a primary write that succeeded")
        assertEquals(listOf(saved), repository.list())
    }

    @Test
    fun `a refused copy never turns a saved land into a failed save`() {
        val storage = InMemoryLocalStore()
        storage.refuseSnapshotWrites = true
        val repository = repository(storage)

        val saved = repository.create(LandDraft("Uno", "El Llano"), 1)

        assertEquals(listOf(saved), repository.list())
        assertTrue(storage.snapshots.isEmpty())
        assertNull(repository.consumeRecovery(), "a primary-only save is not a recovery")
    }

    @Test
    fun `a damaged primary restores the newest fully valid copy and reports it once`() {
        val storage = InMemoryLocalStore()
        val repository = repository(storage)
        val first = repository.create(LandDraft("Uno", "El Llano"), 1)
        val second = repository.create(LandDraft("Dos", "La Vega"), 2)
        repository.create(LandDraft("Tres", "Las Eras"), 3)
        // The newest copy is damaged in place; the previous copy is the newest fully valid one.
        storage.snapshots[0] = damaged(storage.snapshots[0])
        storage.corruptPrimary()

        val reopened = repository(storage)

        assertEquals(listOf(first, second), reopened.list())
        assertEquals(LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY, reopened.consumeRecovery())
        assertNull(reopened.consumeRecovery(), "a recovery is announced once")
        val healed = repository(storage)
        healed.list()
        assertNull(healed.consumeRecovery(), "reopening a healed store is not a recovery")
        storage.snapshots.forEach { copy ->
            assertNotNull(LandSnapshotFormat.unwrap(copy), "a damaged copy is dropped")
        }
        assertEquals(
            LandStoreFormat.encode(LandSnapshot(active = listOf(first, second))),
            storage.value,
            "the recovered aggregate is written back as the primary store",
        )
    }

    @Test
    fun `a copy with one undecodable record is never restored as complete`() {
        val storage = InMemoryLocalStore()
        val repository = repository(storage)
        val kept = repository.create(LandDraft("Uno", "El Llano"), 1)
        storage.snapshots.add(
            0,
            LandSnapshotFormat.wrap(
                """
                land-store-v2
                active
                land-1|Uno|El Llano||DRYLAND|ORGANIC|PICUAL||1.5|85||1|2
                land-2|Rota|El Llano||NO_EXISTE|ORGANIC|PICUAL||1.5|85||3|4
                removed
                """.trimIndent(),
            ),
        )
        storage.corruptPrimary()

        val reopened = repository(storage)

        assertEquals(listOf(kept), reopened.list())
        assertEquals(LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY, reopened.consumeRecovery())
        storage.snapshots.forEach { copy ->
            assertNotNull(LandSnapshotFormat.unwrap(copy), "the partial copy is dropped")
        }
    }

    @Test
    fun `an unreadable primary with no valid copy fails the read instead of opening empty`() {
        val storage = InMemoryLocalStore()
        storage.value = "esto no es un almacén de terrenos"
        val repository = repository(storage)

        assertFailsWith<LandStoreUnreadableException> { repository.list() }
        assertFailsWith<LandStoreUnreadableException> { repository.listRemoved() }
        assertNull(repository.consumeRecovery())
    }

    @Test
    fun `a truncated primary is corruption, not an empty store`() {
        val storage = InMemoryLocalStore()
        val repository = repository(storage)
        repository.create(LandDraft("Uno", "El Llano"), 1)
        // The removed marker is gone: the aggregate was cut short, so it is not an empty store.
        storage.snapshots.clear()
        storage.value = LandStoreFormat.encode(LandSnapshot())
            .replace("\nremoved", "")

        assertFailsWith<LandStoreUnreadableException> { repository.list() }
    }

    @Test
    fun `permanent deletion purges the primary store and every retained copy`() {
        val storage = InMemoryLocalStore()
        val repository = repository(storage)
        val kept = repository.create(LandDraft("Uno", "El Llano"), 1)
        val doomed = repository.create(LandDraft("Dos", "La Vega"), 2)
        assertIs<LandLifecycleResult.Done>(repository.moveToRemoved(doomed.id, now = 3))

        val result = repository.permanentlyDelete(doomed.id)

        assertIs<LandLifecycleResult.Done>(result)
        assertEquals(listOf(kept), repository.list())
        assertTrue(repository.listRemoved().isEmpty())
        assertNull(storage.purgeMarker, "the marker is cleared once every copy is clean")
        assertTrue(storage.snapshots.isNotEmpty())
        storage.snapshots.forEach { copy ->
            val snapshot = assertNotNull(LandSnapshotFormat.unwrap(copy))
            assertTrue(snapshot.active.none { it.id == doomed.id }, "no copy keeps the deleted land")
            assertTrue(snapshot.removed.none { it.land.id == doomed.id })
        }
    }

    @Test
    fun `the durable purge marker is written before the primary store`() {
        val storage = InMemoryLocalStore()
        val repository = repository(storage)
        val doomed = repository.create(LandDraft("Dos", "La Vega"), 1)
        assertIs<LandLifecycleResult.Done>(repository.moveToRemoved(doomed.id, now = 2))
        storage.writes.clear()

        assertIs<LandLifecycleResult.Done>(repository.permanentlyDelete(doomed.id))

        assertEquals("marker", storage.writes.first())
        assertEquals("primary", storage.writes[1])
        assertTrue(storage.writes.last() == "marker", "the marker is the last thing cleared")
        assertNull(storage.purgeMarker)
    }

    @Test
    fun `a copy that cannot be rewritten cannot resurrect a purged land`() {
        val storage = InMemoryLocalStore()
        val repository = repository(storage)
        val kept = repository.create(LandDraft("Uno", "El Llano"), 1)
        val doomed = repository.create(LandDraft("Dos", "La Vega"), 2)
        assertIs<LandLifecycleResult.Done>(repository.moveToRemoved(doomed.id, now = 3))
        storage.refuseSnapshotRewrites = true

        assertIs<LandLifecycleResult.Done>(repository.permanentlyDelete(doomed.id))
        assertNotNull(storage.purgeMarker, "an unsanitized copy keeps the marker")
        // Simulate a crash that left only the stale copies: the clean newest copy disappears and the
        // primary is damaged. The marker still keeps the deleted land out of the restored aggregate.
        storage.snapshots.removeAt(0)
        storage.corruptPrimary()

        val reopened = repository(storage)

        assertEquals(listOf(kept), reopened.list())
        assertTrue(reopened.listRemoved().isEmpty())
        assertNull(
            LandStoreFormat.decode(storage.value)?.removed?.firstOrNull { it.land.id == doomed.id },
        )
    }

    @Test
    fun `a refused permanent delete keeps the durable marker and never brings the land back`() {
        val storage = InMemoryLocalStore()
        val repository = repository(storage)
        val doomed = repository.create(LandDraft("Dos", "La Vega"), 1)
        assertIs<LandLifecycleResult.Done>(repository.moveToRemoved(doomed.id, now = 2))
        storage.refusePrimaryWrites = true

        assertEquals(LandLifecycleResult.StorageFailed, repository.permanentlyDelete(doomed.id))

        assertNotNull(storage.purgeMarker)
        storage.refusePrimaryWrites = false
        assertTrue(repository.listRemoved().isEmpty(), "a read keeps filtering the selected id")
        storage.corruptPrimary()
        val reopened = repository(storage)
        assertTrue(reopened.listRemoved().none { it.land.id == doomed.id })
    }

    @Test
    fun `the purge marker round-trips ids with separators and line breaks`() {
        val ids = setOf("land-1", "land|2", "land%3", "land\n4")

        val decoded = LandPurgeMarkerFormat.decode(LandPurgeMarkerFormat.encode(ids))

        assertEquals(ids, decoded)
        assertEquals(emptySet(), LandPurgeMarkerFormat.decode(null))
        assertEquals(emptySet(), LandPurgeMarkerFormat.decode(""))
    }

    private fun repository(storage: InMemoryLocalStore): LandRepository {
        var next = 0
        return LandRepository(
            storage = storage,
            idGenerator = { "land-${next++}" },
        )
    }

    private fun assertCopyMatchesPrimary(storage: InMemoryLocalStore) {
        assertTrue(storage.snapshots.isNotEmpty(), "a committed change writes one copy")
        assertTrue(storage.snapshots.size <= MAX_AUTOMATIC_LAND_SNAPSHOTS)
        assertEquals(
            LandStoreFormat.decode(storage.value),
            LandSnapshotFormat.unwrap(storage.snapshots.first()),
            "the newest copy holds the aggregate the primary write committed",
        )
    }

    /** A copy whose body still decodes but whose checksum no longer matches. */
    private fun damaged(copy: String): String = copy.replace("|Uno|", "|Un0|")

    private class InMemoryLocalStore : LandStorage, LandSnapshotStorage {
        var value: String? = null
        val snapshots = mutableListOf<String>()
        var purgeMarker: String? = null
        var refusePrimaryWrites = false
        var refuseSnapshotWrites = false
        var refuseSnapshotRewrites = false
        val writes = mutableListOf<String>()

        override fun read(): String? = value

        override fun write(value: String) {
            if (refusePrimaryWrites) error("primary refused")
            writes += "primary"
            this.value = value
        }

        override fun readSnapshots(): List<String> = snapshots.toList()

        override fun writeSnapshot(value: String) {
            if (refuseSnapshotWrites) error("copy refused")
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

        fun corruptPrimary() {
            value = "copia principal dañada"
        }
    }
}
