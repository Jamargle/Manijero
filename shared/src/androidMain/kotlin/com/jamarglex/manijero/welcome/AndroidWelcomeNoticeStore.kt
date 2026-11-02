package com.jamarglex.manijero.welcome

import android.content.Context

/**
 * The Android store for the welcome-dismissed flag. It uses its own private preferences file and a
 * synchronous `commit` so a refused write throws. The flag holds no land or personal data.
 */
class AndroidWelcomeNoticeStore(context: Context) : WelcomeNoticeStore {
    private val preferences = context.applicationContext.getSharedPreferences(
        PREFERENCES_FILE,
        Context.MODE_PRIVATE,
    )

    override fun isDismissed(): Boolean = preferences.getBoolean(KEY, false)

    override fun markDismissed() {
        check(preferences.edit().putBoolean(KEY, true).commit()) { "Could not save the flag" }
    }

    companion object {
        const val PREFERENCES_FILE = "manijero_welcome"
        private const val KEY = "dismissed"
    }
}
