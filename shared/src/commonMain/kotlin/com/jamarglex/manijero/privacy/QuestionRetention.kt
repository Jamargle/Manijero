package com.jamarglex.manijero.privacy

import com.jamarglex.manijero.lands.Land

/**
 * The longest time a retained question and answer may be kept, in days. The service deletes a
 * record no later than this; the on-screen copy states the same number.
 */
const val RETENTION_MAX_DAYS = 30

/**
 * Whether a question the person explicitly allowed to be kept may be sent with
 * `retain_for_improvement: true`.
 *
 * The service never receives a land's name, zone, custom variety, or notes, so it cannot remove
 * them from retained text, and it sees a municipality only when a question needs it. The device can:
 * if the wording contains a stored land's name, zone, municipality, custom variety, or notes
 * (case-insensitive, values of two or more characters), the permission is dropped and
 * the question is sent without it. This only ever retains *less* than the person allowed; it never
 * changes the question or the answer. Standard-library only.
 */
fun retentionAllowedFor(question: String, lands: List<Land>): Boolean {
    val wording = question.lowercase()
    return lands.none { land ->
        listOfNotNull(land.name, land.zone, land.municipality, land.varietyOther, land.notes)
            .map { value -> value.trim().lowercase() }
            .any { value -> value.length >= 2 && wording.contains(value) }
    }
}
