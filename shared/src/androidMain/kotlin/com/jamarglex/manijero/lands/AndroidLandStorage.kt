package com.jamarglex.manijero.lands

import android.content.Context

/**
 * The Android land store: the whole aggregate is one `SharedPreferences` value written with a
 * synchronous `commit`, so a lifecycle transition is never half persisted and a failed commit throws
 * instead of reporting a save that did not happen.
 */
class SharedPreferencesLandStorage(context: Context) : LandStorage {
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

    private companion object { const val KEY = "land_store" }
}
