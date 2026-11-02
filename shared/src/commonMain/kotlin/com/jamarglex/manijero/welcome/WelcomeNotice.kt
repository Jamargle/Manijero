package com.jamarglex.manijero.welcome

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/** The device-local flag that the welcome card was dismissed. Either call may throw. */
interface WelcomeNoticeStore {
    fun isDismissed(): Boolean
    fun markDismissed()
}

/**
 * The welcome card state. An unreadable store means "not dismissed", so the card shows. A refused
 * write still hides the card for this session. Nothing is logged and no error is shown.
 */
class WelcomeNotice(private val store: WelcomeNoticeStore) {
    var visible: Boolean by mutableStateOf(!runCatching { store.isDismissed() }.getOrDefault(false))
        private set

    fun dismiss() {
        visible = false
        runCatching { store.markDismissed() }
    }

    /** Shows the card again in memory only; nothing is written. */
    fun showAgain() {
        visible = true
    }
}

/** Each welcome string key and the accepted string keys its facts come from (copy guard input). */
val WELCOME_COPY_SOURCES: Map<String, List<String>> = mapOf(
    "welcome_title" to emptyList(),
    "welcome_can" to listOf("coverage_intro"),
    "welcome_limits" to listOf("coverage_no_personal", "coverage_no_coop", "coverage_help_body"),
    "welcome_privacy" to listOf("chat_home_privacy_summary", "privacy_promise_body_2"),
    "welcome_lands" to listOf("chat_home_description"),
)
