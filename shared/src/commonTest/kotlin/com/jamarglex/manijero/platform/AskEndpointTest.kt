package com.jamarglex.manijero.platform

import kotlin.test.Test
import kotlin.test.assertEquals

class AskEndpointTest {
    @Test
    fun usesPlatformDefaultWhenNoOverrideIsConfigured() {
        assertEquals(
            "http://10.0.2.2:8000",
            selectAskBaseUrl(null, defaultBaseUrl = "http://10.0.2.2:8000"),
        )
    }

    @Test
    fun prefersPrimaryOverrideOverSecondaryAndDefault() {
        assertEquals(
            "http://primary:8001",
            selectAskBaseUrl(
                primaryOverride = "http://primary:8001",
                secondaryOverride = "http://secondary:8002",
                defaultBaseUrl = "http://127.0.0.1:8000",
            ),
        )
    }

    @Test
    fun fallsBackToSecondaryOverrideWhenPrimaryIsBlank() {
        assertEquals(
            "http://environment:8002",
            selectAskBaseUrl(
                primaryOverride = " ",
                secondaryOverride = "http://environment:8002",
                defaultBaseUrl = "http://127.0.0.1:8000",
            ),
        )
    }
}
