package com.jamarglex.manijero.privacy

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class FileImprovementConsentStoreTest {
    private val directory = Files.createTempDirectory("manijero-consent")

    @Test
    fun missingFileIsOff() = assertFalse(FileImprovementConsentStore(directory.resolve("c.txt")).isEnabled())

    @Test
    fun onAndOffSurviveANewInstance() {
        val path = directory.resolve("sub/c.txt")
        FileImprovementConsentStore(path).setEnabled(true)
        assertTrue(FileImprovementConsentStore(path).isEnabled())
        FileImprovementConsentStore(path).setEnabled(false)
        assertFalse(FileImprovementConsentStore(path).isEnabled())
    }

    @Test
    fun anythingButExactlyOnIsOff() {
        val path = directory.resolve("c.txt")
        listOf("", "ON\n", "yes\non\n", " on\n").forEach { content ->
            Files.writeString(path, content)
            assertFalse(FileImprovementConsentStore(path).isEnabled(), content)
        }
    }

    @Test
    fun blockedDirectoryThrowsOnWrite() {
        val blocker = directory.resolve("blocker")
        Files.writeString(blocker, "x")
        assertFailsWith<Exception> { FileImprovementConsentStore(blocker.resolve("c.txt")).setEnabled(true) }
    }

    @Test
    fun defaultPathIsUnderTheManijeroFolder() {
        val path = desktopImprovementConsentPath("/home/x")
        assertEquals("improvement-consent-v1.txt", path.fileName.toString())
        assertEquals(".manijero", path.parent.fileName.toString())
    }
}
