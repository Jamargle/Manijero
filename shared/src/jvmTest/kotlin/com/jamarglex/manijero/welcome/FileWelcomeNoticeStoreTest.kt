package com.jamarglex.manijero.welcome

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class FileWelcomeNoticeStoreTest {
    private val directory = Files.createTempDirectory("manijero-welcome")

    @Test
    fun missingFileIsNotDismissed() = assertFalse(FileWelcomeNoticeStore(directory.resolve("w.txt")).isDismissed())

    @Test
    fun markedFlagSurvivesANewInstance() {
        val path = directory.resolve("sub/w.txt")
        FileWelcomeNoticeStore(path).markDismissed()
        assertTrue(FileWelcomeNoticeStore(path).isDismissed())
    }

    @Test
    fun garbageContentIsNotDismissed() {
        val path = directory.resolve("w.txt")
        Files.writeString(path, "yes\ndismissed\n")
        assertFalse(FileWelcomeNoticeStore(path).isDismissed())
    }

    @Test
    fun blockedDirectoryThrowsOnWrite() {
        val blocker = directory.resolve("blocker")
        Files.writeString(blocker, "x")
        assertFailsWith<Exception> { FileWelcomeNoticeStore(blocker.resolve("w.txt")).markDismissed() }
    }

    @Test
    fun defaultPathIsUnderTheManijeroFolder() {
        assertEquals("welcome-v1.txt", desktopWelcomeStorePath("/home/x").fileName.toString())
    }
}
