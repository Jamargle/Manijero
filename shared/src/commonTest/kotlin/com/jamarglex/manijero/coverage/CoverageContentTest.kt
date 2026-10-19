package com.jamarglex.manijero.coverage

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class CoverageContentTest {
    // Reviewed expectation, intentionally independent from CoverageContent.kt's lists.
    private val reviewedCorpusTopics = setOf(
        "coverage_topic_application", "coverage_topic_sigpac", "coverage_topic_olive_aid",
        "coverage_topic_procedure", "coverage_topic_notifications",
    )

    @Test fun disclosureHasAllSectionsAndTopicsMatchReviewedCorpus() {
        assertEquals(3, COVERAGE_SECTIONS.size)
        assertTrue(COVERAGE_SECTIONS.all { it.bodyKeys.isNotEmpty() })
        assertEquals(reviewedCorpusTopics, COVERED_TOPIC_KEYS.toSet())
        assertTrue("coverage_not_yet_topics" in NOT_ANSWERED_KEYS)
        val everyDisplayedKey = setOf(
            "coverage_title", "coverage_intro", "coverage_section_topics", "coverage_section_limits",
            "coverage_section_help", "coverage_privacy_link", "privacy_back", "coverage_help_body",
        ) + COVERED_TOPIC_KEYS + NOT_ANSWERED_KEYS
        val modeledKeys = COVERAGE_SECTIONS.flatMap { listOf(it.titleKey) + it.bodyKeys }.toSet()
        assertTrue(modeledKeys.containsAll(COVERED_TOPIC_KEYS + NOT_ANSWERED_KEYS))
        assertTrue(everyDisplayedKey.all { it.isNotBlank() })
        assertTrue((COVERED_TOPIC_KEYS + NOT_ANSWERED_KEYS).all { it.none(Char::isDigit) })
    }
}
