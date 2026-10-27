package com.jamarglex.manijero.lands

/**
 * How many same-device automatic copies of the land aggregate are retained.
 *
 * Each copy is one complete encoded aggregate, so the retained copies cost at most this many times
 * the store the person already has. Three copies keep a recent change, the state before it, and one
 * older state without letting the app grow an unbounded history.
 */
const val MAX_AUTOMATIC_LAND_SNAPSHOTS: Int = 3

/**
 * The same-device copies and the durable purge marker that live next to the primary land store.
 *
 * Every method is local storage only: an implementation MUST NOT use a network, an operating-system
 * cloud backup destination, or any account. Copies are written by [LandRepository] only after the
 * primary aggregate write succeeded, and they are rotated so the retained count stays bounded.
 *
 * The purge marker is the durable record of a permanent deletion. It is written before the primary
 * store is rewritten and cleared only after the primary and every retained copy are sanitized, so a
 * crash cannot let a stale copy bring a deleted land back.
 */
interface LandSnapshotStorage {
    /** The retained copies, newest first. Each value is one [LandSnapshotFormat] value. */
    fun readSnapshots(): List<String>

    /**
     * Stores [value] as the newest copy, pushing the previous ones down and dropping anything beyond
     * [MAX_AUTOMATIC_LAND_SNAPSHOTS].
     */
    fun writeSnapshot(value: String)

    /**
     * Replaces every retained copy with `values` (newest first), dropping the ones beyond
     * [MAX_AUTOMATIC_LAND_SNAPSHOTS] and any copy no longer in the list.
     */
    fun replaceSnapshots(values: List<String>)

    /** The encoded purge marker, or `null` when nothing is pending. */
    fun readPurgeMarker(): String?

    /** Stores the encoded purge marker, or clears it when [value] is `null`. */
    fun writePurgeMarker(value: String?)
}

/**
 * What a store read had to do beyond opening the primary aggregate.
 *
 * It is a plain outcome, not an error: the lands were recovered, so the app can say so and continue.
 * Nothing here is ever inferred from a failed or empty read.
 */
enum class LandStoreRecovery {
    /** The primary copy could not be read; the newest fully valid same-device copy was restored. */
    RESTORED_FROM_AUTOMATIC_COPY,
}

/**
 * The primary aggregate and every retained automatic copy are unreadable.
 *
 * It is thrown instead of returning an empty store, because an unreadable store is not an empty one:
 * the person must see a failed read with a retry, never a list that silently forgot their lands.
 * The message carries no land name, record, or timestamp.
 */
class LandStoreUnreadableException :
    Exception("The local land store and its automatic copies are unreadable")

/**
 * One automatic copy: integrity metadata plus one complete `land-store-v2` aggregate.
 *
 * ```text
 * manijero-land-snapshot-1
 * checksum=<FNV-1a 64 of everything after this line>
 * land-store-v2
 * active
 * …
 * removed
 * …
 * ```
 *
 * The checksum catches a copy damaged in place, and the body is decoded with
 * `requireEveryRecord = true`, so a partially readable copy is never offered as a complete one.
 */
internal object LandSnapshotFormat {
    private const val HEADER = "manijero-land-snapshot-1"
    private const val CHECKSUM_PREFIX = "checksum="
    private const val OFFSET_BASIS = -3750763034362895579L // FNV-1a 64-bit
    private const val PRIME = 1099511628211L

    /** Wraps one encoded aggregate as a complete automatic copy. */
    fun wrap(store: String): String = buildString {
        append(HEADER)
        append('\n')
        append(CHECKSUM_PREFIX)
        append(checksum(store))
        append('\n')
        append(store)
    }

    /** The fully valid aggregate this copy holds, or `null` when the copy is damaged anywhere. */
    fun unwrap(value: String?): LandSnapshot? {
        if (value.isNullOrEmpty()) return null
        val lines = value.lineSequence().toList()
        if (lines.size < 3) return null
        if (lines[0] != HEADER) return null
        val declared = lines[1]
        if (!declared.startsWith(CHECKSUM_PREFIX)) return null
        val store = lines.drop(2).joinToString("\n")
        if (declared.removePrefix(CHECKSUM_PREFIX) != checksum(store)) return null
        return LandStoreFormat.decode(store, requireEveryRecord = true)
    }

    private fun checksum(value: String): String {
        var hash = OFFSET_BASIS
        value.forEach { character ->
            hash = hash xor character.code.toLong()
            hash *= PRIME
        }
        return hash.toULong().toString(16)
    }
}

/**
 * The durable set of land ids a permanent deletion selected.
 *
 * Ids are encoded one per line with the store's own token escaping, so an id containing a separator
 * round-trips. An empty value means nothing is pending.
 */
internal object LandPurgeMarkerFormat {
    fun encode(ids: Set<String>): String = ids.sorted().joinToString("\n", transform = LandStoreFormat::escapeToken)

    fun decode(value: String?): Set<String> {
        if (value.isNullOrEmpty()) return emptySet()
        return value.lineSequence()
            .filter { line -> line.isNotEmpty() }
            .map(LandStoreFormat::unescapeToken)
            .toSet()
    }
}
