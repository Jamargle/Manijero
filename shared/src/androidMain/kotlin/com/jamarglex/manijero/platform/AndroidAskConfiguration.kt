package com.jamarglex.manijero.platform

private const val ANDROID_EMULATOR_ASK_BASE_URL = "http://10.0.2.2:8000"

fun androidAskBaseUrl(gradleProperty: String?): String = selectAskBaseUrl(
    primaryOverride = gradleProperty,
    defaultBaseUrl = ANDROID_EMULATOR_ASK_BASE_URL,
)
