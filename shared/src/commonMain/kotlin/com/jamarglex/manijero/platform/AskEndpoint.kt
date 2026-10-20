package com.jamarglex.manijero.platform

/** Selects an endpoint from platform-provided overrides, then its platform default. */
fun selectAskBaseUrl(
    primaryOverride: String?,
    secondaryOverride: String? = null,
    defaultBaseUrl: String,
): String = primaryOverride?.takeIf(String::isNotBlank)
    ?: secondaryOverride?.takeIf(String::isNotBlank)
    ?: defaultBaseUrl
