package com.jamarglex.manijero.connection

import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.createDirectories
import kotlin.io.path.listDirectoryEntries
import kotlin.io.path.readText
import kotlin.io.path.writeText
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** The Desktop address file, in a temporary directory: round trip, clear, and no partial files. */
class FileServiceAddressStoreTest {
    private val root: Path = Files.createTempDirectory("manijero-connection")
    private val file: Path = root.resolve(".manijero").resolve("connection-v1.txt")

    @AfterTest
    fun cleanUp() {
        root.toFile().deleteRecursively()
    }

    @Test
    fun `a missing file has no saved address`() {
        assertNull(FileServiceAddressStore(file).load())
    }

    @Test
    fun `an address round trips as one utf-8 line and clear removes it`() {
        val store = FileServiceAddressStore(file)
        store.save("http://192.168.1.20:8000")

        assertEquals("http://192.168.1.20:8000\n", file.readText(Charsets.UTF_8))
        assertEquals("http://192.168.1.20:8000", FileServiceAddressStore(file).load())

        store.save("https://qa.example.org/api")
        assertEquals("https://qa.example.org/api", store.load())

        store.clear()
        assertFalse(Files.exists(file))
        assertNull(store.load())
        store.clear()
    }

    @Test
    fun `only the first line is read`() {
        file.parent.createDirectories()
        file.writeText("http://10.0.0.5:8000\nleftover\n")
        assertEquals("http://10.0.0.5:8000", FileServiceAddressStore(file).load())
    }

    @Test
    fun `a failed write throws and leaves no partial or temporary file`() {
        val store = FileServiceAddressStore(file)
        store.save("http://192.168.1.20:8000")
        // A directory where the file should be makes the final move fail.
        val blocked = root.resolve("blocked").resolve("connection-v1.txt")
        blocked.createDirectories()
        Files.writeString(blocked.resolve("keep"), "x")

        assertFailsWith<Exception> { FileServiceAddressStore(blocked).save("http://10.0.0.5:8000") }

        assertEquals(listOf("connection-v1.txt"), blocked.parent.listDirectoryEntries().map { it.fileName.toString() })
        assertEquals(listOf("connection-v1.txt"), file.parent.listDirectoryEntries().map { it.fileName.toString() })
        assertTrue(Files.isDirectory(blocked))
        assertEquals("http://192.168.1.20:8000", store.load())
    }
}
