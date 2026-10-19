package com.jamarglex.manijero.coverage

/** Pinned disclosure. Keep covered areas aligned with the reviewed seed corpus. */
data class CoverageSection(val titleKey: String, val bodyKeys: List<String>)

val COVERED_TOPIC_KEYS = listOf(
    "coverage_topic_application", "coverage_topic_sigpac", "coverage_topic_olive_aid",
    "coverage_topic_procedure", "coverage_topic_notifications",
)
val NOT_ANSWERED_KEYS = listOf(
    "coverage_no_coop", "coverage_no_personal", "coverage_no_outside", "coverage_no_unrelated",
    "coverage_not_yet_topics",
)
val COVERAGE_SECTIONS = listOf(
    CoverageSection("coverage_section_topics", COVERED_TOPIC_KEYS),
    CoverageSection("coverage_section_limits", NOT_ANSWERED_KEYS),
    CoverageSection("coverage_section_help", listOf("coverage_help_body")),
)
