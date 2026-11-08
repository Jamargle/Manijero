package com.jamarglex.manijero.privacy

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * The device-local `Ayúdanos a mejorar` choice. It holds one on/off value and no question, answer,
 * land or personal data. Either call may throw.
 */
interface ImprovementConsentStore {
    fun isEnabled(): Boolean
    fun setEnabled(enabled: Boolean)
}

/**
 * The standing permission to keep sent questions and answers for product improvement.
 *
 * It is off unless the store explicitly says on: an unreadable store, or no store at all (the iOS
 * scaffold and previews), means off, so a failure can never turn retention on. A refused write still
 * applies the new value for this session only; nothing is logged and no error is shown.
 */
class ImprovementConsent(private val store: ImprovementConsentStore?) {
    var enabled: Boolean by mutableStateOf(
        store?.let { runCatching { it.isEnabled() }.getOrDefault(false) } ?: false,
    )
        private set

    fun update(value: Boolean) {
        enabled = value
        store?.let { runCatching { it.setEnabled(value) } }
    }
}
