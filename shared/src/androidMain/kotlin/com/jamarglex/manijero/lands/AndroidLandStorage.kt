package com.jamarglex.manijero.lands

import android.content.Context
import android.content.SharedPreferences

/**
 * The Android land store: the whole aggregate is one `SharedPreferences` value written with a
 * synchronous `commit`, so a lifecycle transition is never half persisted and a failed commit throws
 * instead of reporting a save that did not happen.
 *
 * The bounded automatic copies live in the same private preferences file, newest in
 * `land_store_snapshot_1` to `land_store_snapshot_3`, and the durable purge marker in
 * `land_store_purge`. They stay in this app's private storage: no network call and no operating
 * system cloud-backup destination is involved.
 */
class SharedPreferencesLandStorage(context: Context) : LandStorage, LandSnapshotStorage {
    private val preferences = context.applicationContext.getSharedPreferences(
        "manijero_lands",
        Context.MODE_PRIVATE,
    )

    override fun read(): String? = preferences.getString(KEY, null)

    override fun write(value: String) {
        check(preferences.edit().putString(KEY, value).commit()) {
            "Could not persist local lands"
        }
    }

    override fun readSnapshots(): List<String> =
        (1..MAX_AUTOMATIC_LAND_SNAPSHOTS).mapNotNull { slot ->
            preferences.getString(snapshotKey(slot), null)
        }

    override fun writeSnapshot(value: String) {
        val editor = preferences.edit()
        for (slot in MAX_AUTOMATIC_LAND_SNAPSHOTS downTo 2) {
            val previous = preferences.getString(snapshotKey(slot - 1), null)
            if (previous == null) {
                editor.remove(snapshotKey(slot))
            } else {
                editor.putString(snapshotKey(slot), previous)
            }
        }
        editor.putString(snapshotKey(1), value)
        check(editor.commit()) { "Could not persist the automatic land copy" }
    }

    override fun replaceSnapshots(values: List<String>) {
        val retained = values.take(MAX_AUTOMATIC_LAND_SNAPSHOTS)
        val editor = preferences.edit()
        retained.forEachIndexed { index, value ->
            editor.putString(snapshotKey(index + 1), value)
        }
        for (slot in retained.size + 1..MAX_AUTOMATIC_LAND_SNAPSHOTS) {
            editor.remove(snapshotKey(slot))
        }
        check(editor.commit()) { "Could not rewrite the automatic land copies" }
    }

    override fun readPurgeMarker(): String? = preferences.getString(KEY_PURGE, null)

    override fun writePurgeMarker(value: String?) {
        val editor = preferences.edit()
        if (value == null) editor.remove(KEY_PURGE) else editor.putString(KEY_PURGE, value)
        check(editor.commit()) { "Could not persist the land purge marker" }
    }

    private fun snapshotKey(slot: Int): String = "land_store_snapshot_$slot"

    private companion object {
        const val KEY = "land_store"
        const val KEY_PURGE = "land_store_purge"
    }
}
