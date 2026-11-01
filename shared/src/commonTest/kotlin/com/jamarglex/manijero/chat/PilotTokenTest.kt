package com.jamarglex.manijero.chat

import io.ktor.http.Url
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Fake tokens only: none of these values is, or was ever, a real pilot credential. */
class PilotTokenTest {
    private val fake = "fakeTokenForTestsOnly-0123456789abcdefABCDEF"

    @Test
    fun `no setting or a blank setting gives no token`() {
        listOf(null, "", " ", "\n", "\t  \n").forEach { raw ->
            assertNull(PilotToken.fromBuildSetting(raw), "\"$raw\" must give no token")
        }
    }

    @Test
    fun `the length bounds are 32 to 512 characters inclusive`() {
        assertNull(PilotToken.fromBuildSetting("a".repeat(31)))
        assertNotNull(PilotToken.fromBuildSetting("a".repeat(32)))
        assertNotNull(PilotToken.fromBuildSetting("a".repeat(512)))
        assertNull(PilotToken.fromBuildSetting("a".repeat(513)))
    }

    @Test
    fun `every b64token character and trailing padding is accepted`() {
        assertNotNull(PilotToken.fromBuildSetting("AZaz09-._~+/AZaz09-._~+/AZaz09-._~+/"))
        assertNotNull(PilotToken.fromBuildSetting("${fake}=="))
    }

    @Test
    fun `whitespace, line breaks, foreign characters, and inner padding are refused`() {
        listOf(
            "$fake extra",
            "$fake\nextra",
            " $fake",
            "$fake\n",
            "${fake}ñ",
            "${fake}é",
            "$fake😀",
            "${fake}\"",
            "$fake;x",
            "abc=$fake",
            "${fake}=x",
        ).forEach { raw ->
            assertNull(PilotToken.fromBuildSetting(raw), "a malformed value must give no token")
        }
    }

    @Test
    fun `toString never contains the value`() {
        val token = assertNotNull(PilotToken.fromBuildSetting(fake))
        assertEquals("PilotToken(redacted)", token.toString())
        assertEquals("PilotToken(redacted)", "$token")
        assertFalse(fake in token.toString())
    }

    @Test
    fun `the bearer header value is the scheme and the exact token`() {
        val token = assertNotNull(PilotToken.fromBuildSetting(fake))
        assertEquals("Bearer $fake", token.bearerHeaderValue())
    }

    @Test
    fun `https and http to this computer may carry the token`() {
        listOf(
            "https://api.example.invalid/ask",
            "https://192.168.1.20:8443/ask",
            "http://localhost:8000/ask",
            "http://LOCALHOST:8000/ask",
            "http://127.0.0.1:8000/ask",
            "http://[::1]:8000/ask",
            "http://10.0.2.2:8000/ask",
        ).forEach { address ->
            assertTrue(mayCarryPilotToken(Url(address)), "$address may carry the token")
        }
    }

    @Test
    fun `cleartext to any other host never carries the token`() {
        listOf(
            "http://192.168.1.20:8000/ask",
            "http://10.0.2.3:8000/ask",
            "http://127.0.0.1.example/ask",
            "http://localhost.evil/ask",
            "http://localhost@evil.example/ask",
            "http://api.example.invalid/ask",
            "ws://localhost:8000/ask",
        ).forEach { address ->
            assertFalse(mayCarryPilotToken(Url(address)), "$address must not carry the token")
        }
    }
}
