package com.jamarglex.manijero.platform

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNull

/** Fake resources only: no build output, no home folder. */
class DesktopEnvironmentTest {
    private fun environmentOf(text: String?): DesktopEnvironment = desktopEnvironment { text }

    @Test
    fun `a missing resource is a local run`() {
        val requested = mutableListOf<String>()
        val environment = desktopEnvironment { name -> requested += name; null }

        assertEquals(DesktopEnvironment.Local, environment)
        assertEquals(listOf("manijero/environment.properties"), requested)
        assertEquals("Manijero", environment.title)
        assertEquals(".manijero", environment.dataFolder)
    }

    @Test
    fun `the default classpath reader finds no resource in the test classpath`() {
        assertEquals(DesktopEnvironment.Local, desktopEnvironment())
    }

    @Test
    fun `a local resource parses`() {
        assertEquals(DesktopEnvironment.Local, environmentOf("environment=local\n"))
    }

    @Test
    fun `a qa resource gives its own title, data folder, and address`() {
        val environment = environmentOf("environment=qa\naskBaseUrl=https://qa.example.org:8443/api\n")

        assertIs<DesktopEnvironment.Qa>(environment)
        assertEquals("Manijero QA", environment.title)
        assertEquals(".manijero-qa", environment.dataFolder)
        assertEquals("https://qa.example.org:8443/api", environment.defaultAskBaseUrl())
    }

    @Test
    fun `qa ignores the runtime address overrides`() {
        val environment = environmentOf("environment=qa\naskBaseUrl=https://qa.manijero.invalid\n")
        val before = System.getProperty("manijero.ask.baseUrl")
        System.setProperty("manijero.ask.baseUrl", "http://127.0.0.1:9999")
        try {
            assertEquals("https://qa.manijero.invalid", environment.defaultAskBaseUrl())
        } finally {
            if (before == null) System.clearProperty("manijero.ask.baseUrl") else System.setProperty("manijero.ask.baseUrl", before)
        }
    }

    @Test
    fun `a present but malformed resource is refused with a plain message that does not echo it`() {
        listOf(
            "environment=prod\n",
            "environment=QA\naskBaseUrl=https://qa.example.org\n",
            "environment=qa\n",
            "environment=qa\naskBaseUrl=http://qa.example.org\n",
            "environment=qa\naskBaseUrl=https://qa.example.org\naskBaseUrl=https://other.example.org\n",
            "environment=qa\nenvironment=local\naskBaseUrl=https://qa.example.org\n",
            "environment=local\naskBaseUrl=https://qa.example.org\n",
            "environment=qa\naskBaseUrl=https://qa.example.org\nextra=1\n",
            "garbage-NOT-AN-ENV\n",
            "",
        ).forEach { text ->
            val error = assertFailsWith<DesktopEnvironmentException>("refused: $text") { environmentOf(text) }
            assertEquals(false, "NOT-AN-ENV" in (error.message ?: ""))
        }
    }

    @Test
    fun `addresses are trimmed and checked`() {
        assertEquals("https://qa.example.org", validQaAddress("  https://qa.example.org/ \n"))
        assertEquals("https://qa.example.org:65535/a/b", validQaAddress("https://qa.example.org:65535/a/b"))
        listOf(
            null, "", "   ", "http://qa.example.org", "https://", "https://user@qa.example.org",
            "https://qa.example.org?x=1", "https://qa.example.org#top", "https://qa .example.org",
            "https://qa.example.org:0", "https://qa.example.org:65536", "https://qa.example.org:123456",
            "ftp://qa.example.org", "https://-bad.example.org", "https://qa.example.org/" + "a".repeat(512),
        ).forEach { assertNull(validQaAddress(it), "must be refused: $it") }
    }
}
