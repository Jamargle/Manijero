package com.jamarglex.manijero.platform

import com.jamarglex.manijero.connection.DESKTOP_TEST_BUILD_PROPERTY
import com.jamarglex.manijero.connection.desktopTestBuildEnabled
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Repo-level guard for the owner decision that the `Conexión` test tools never reach a release
 * build. It reads the checked-in Android variant sources and the Desktop build script, so it runs in
 * the ordinary `:shared:jvmTest` tier without an SDK, emulator, or packaged app.
 */
class TestBuildGatingGuardTest {
    private val root = repositoryRoot()

    @Test
    fun `the android release source set returns no tools and names nothing from connection`() {
        val release = root.resolve("androidApp/src/release/kotlin/com/jamarglex/manijero/TestBuildTools.kt")
        assertTrue(release.isFile, "missing $release")
        val text = release.readText()
        assertTrue("fun testBuildConnectionTools(" in text)
        assertTrue(Regex("""\)\s*:\s*Nothing\?\s*=\s*null""").containsMatchIn(text), "release must return null")
        val imports = text.lines().filter { it.trimStart().startsWith("import ") }
        assertTrue(imports.none { "connection" in it }, "release imports nothing from connection: $imports")
        assertFalse("com.jamarglex.manijero.connection" in text, "release must not reference the connection package")
        val forbidden = Regex("""\b(ConnectionTools|ActiveServiceAddress|\w*ServiceAddressStore|\w*StatusChecker|ConnectionScreen)\b""")
        assertEquals(emptyList(), forbidden.findAll(text).map { it.value }.toList(), "release builds no tools")
    }

    @Test
    fun `the android debug source set builds the tools`() {
        val debug = root.resolve("androidApp/src/debug/kotlin/com/jamarglex/manijero/TestBuildTools.kt")
        assertTrue(debug.isFile, "missing $debug")
        val text = debug.readText()
        assertTrue("fun testBuildConnectionTools(" in text)
        assertTrue("AndroidServiceAddressStore(" in text)
    }

    @Test
    fun `the android main source set never names the screen or the store`() {
        val main = root.resolve("androidApp/src/main")
        val offenders = main.walkTopDown()
            .filter { it.isFile && (it.extension == "kt" || it.extension == "xml") }
            .filter { file ->
                val text = file.readText()
                "ConnectionScreen" in text || "AndroidServiceAddressStore" in text
            }
            .toList()
        assertEquals(emptyList(), offenders)
    }

    @Test
    fun `the desktop test-build property is set only on the run task`() {
        val script = root.resolve("desktopApp/build.gradle.kts").readText()
        val runBlockStart = Regex("""tasks\.withType<JavaExec>\(\)\.matching \{ it\.name == "run" \}\.configureEach \{""")
            .find(script) ?: error("desktopApp/build.gradle.kts must configure the run task by name")
        val runBlock = bracedBlock(script, runBlockStart.range.last)
        assertTrue(
            "systemProperty(\"$DESKTOP_TEST_BUILD_PROPERTY\", \"true\")" in runBlock,
            "the run task must set $DESKTOP_TEST_BUILD_PROPERTY",
        )

        // Everything else, including `application`, `nativeDistributions`, and any `runRelease` or
        // `runDistributable` configuration, must not carry the flag.
        val closingBrace = runBlockStart.range.last + runBlock.length + 1
        val outsideRun = script.removeRange(runBlockStart.range.first, closingBrace + 1)
        assertFalse(DESKTOP_TEST_BUILD_PROPERTY in outsideRun, "the property must not appear outside the run task")
        assertFalse("jvmArgs" in script, "no jvmArgs may carry a test-build flag into a package")
        assertEquals(1, Regex(Regex.escape(DESKTOP_TEST_BUILD_PROPERTY)).findAll(script).count())
    }

    @Test
    fun `the desktop flag is on only for the exact value true`() {
        assertTrue(desktopTestBuildEnabled("true"))
        listOf(null, "", "TRUE", "True", " true", "1", "yes", "false").forEach { value ->
            assertFalse(desktopTestBuildEnabled(value), "\"$value\" must not enable test tools")
        }
    }

    /** The text between the `{` at [openIndex] and its matching `}`, both excluded. */
    private fun bracedBlock(text: String, openIndex: Int): String {
        require(text[openIndex] == '{')
        var depth = 0
        for (index in openIndex until text.length) {
            when (text[index]) {
                '{' -> depth++
                '}' -> if (--depth == 0) return text.substring(openIndex + 1, index)
            }
        }
        error("unbalanced braces after index $openIndex")
    }

    private fun repositoryRoot(): File {
        var directory: File? = File("").absoluteFile
        while (directory != null) {
            if (File(directory, "androidApp/src/main/AndroidManifest.xml").isFile) return directory
            directory = directory.parentFile
        }
        error("Could not locate the repository root from ${File("").absolutePath}")
    }
}
