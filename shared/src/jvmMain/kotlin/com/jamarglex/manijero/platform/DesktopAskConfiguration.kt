package com.jamarglex.manijero.platform

private const val DESKTOP_ASK_BASE_URL = "http://127.0.0.1:8000"

fun desktopAskBaseUrl(
    systemProperty: String? = System.getProperty("manijero.ask.baseUrl"),
    environmentVariable: String? = System.getenv("MANIJERO_ASK_BASE_URL"),
): String = selectAskBaseUrl(
    primaryOverride = systemProperty,
    secondaryOverride = environmentVariable,
    defaultBaseUrl = DESKTOP_ASK_BASE_URL,
)
