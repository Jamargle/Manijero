package com.jamarglex.manijero.platform

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

/** Fake tokens only. */
class DesktopPilotTokenTest {
    private val fake = "fakeTokenForTestsOnly-0123456789abcdefABCDEF"

    @Test
    fun `a present resource gives the token, read from the generated resource name`() {
        val requested = mutableListOf<String>()
        val token = desktopPilotToken { name -> requested += name; "$fake\n" }

        assertNotNull(token)
        assertEquals("Bearer $fake", token.bearerHeaderValue())
        assertEquals(listOf("manijero/pilot-token.txt"), requested)
    }

    @Test
    fun `an absent, blank, or malformed resource gives no token`() {
        listOf(null, "", "  \n", "short", "$fake with space", "$fake\nsecond-line").forEach { content ->
            assertNull(desktopPilotToken { content }, "this resource must give no token")
        }
    }

    @Test
    fun `the default classpath reader finds no token in the test classpath`() {
        assertNull(desktopPilotToken())
    }
}
