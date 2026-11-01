package com.jamarglex.manijero.connection

import android.content.Context

/**
 * The Android test-build store for the remembered answer-service address. It uses its own private
 * preferences file, separate from the land store, and a synchronous `commit` so a refused write
 * throws instead of reporting a save that did not happen. Release builds never construct it.
 */
class AndroidServiceAddressStore(context: Context) : ServiceAddressStore {
    private val preferences = context.applicationContext.getSharedPreferences(
        PREFERENCES_FILE,
        Context.MODE_PRIVATE,
    )

    override fun load(): String? = preferences.getString(KEY, null)

    override fun save(address: String) {
        check(preferences.edit().putString(KEY, address).commit()) { "Could not save the address" }
    }

    override fun clear() {
        check(preferences.edit().remove(KEY).commit()) { "Could not clear the address" }
    }

    companion object {
        const val PREFERENCES_FILE = "manijero_connection"
        private const val KEY = "answer_service_address"
    }
}
