package com.jamarglex.manijero.privacy

import android.content.Context

/**
 * The Android store for the `Ayúdanos a mejorar` choice. It uses its own private preferences file
 * and a synchronous `commit` so a refused write throws. It holds one boolean and no personal data.
 */
class AndroidImprovementConsentStore(context: Context) : ImprovementConsentStore {
    private val preferences = context.applicationContext.getSharedPreferences(
        PREFERENCES_FILE,
        Context.MODE_PRIVATE,
    )

    override fun isEnabled(): Boolean = preferences.getBoolean(KEY, false)

    override fun setEnabled(enabled: Boolean) {
        check(preferences.edit().putBoolean(KEY, enabled).commit()) { "Could not save the choice" }
    }

    companion object {
        const val PREFERENCES_FILE = "manijero_improvement_consent"
        private const val KEY = "enabled"
    }
}
