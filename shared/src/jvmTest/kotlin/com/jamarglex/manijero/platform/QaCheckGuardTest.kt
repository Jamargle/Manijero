package com.jamarglex.manijero.platform

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Repo-level guard for the QA Desktop check (`qa_real_device_check`): the live class never runs in
 * an ordinary tier, and the QA access key reaches the check only as the build-generated classpath
 * resource added to one named test task, never as a JVM property, environment entry, or argument.
 * It reads checked-in files only, never a key file.
 */
class QaCheckGuardTest {
    private val root = repositoryRoot()
    private val sharedScript = root.resolve("shared/build.gradle.kts").readText()

    @Test
    fun `the live qa check is excluded from jvmTest and runs only through its own task`() {
        val jvmTest = sharedScript.substringAfter("tasks.named<Test>(\"jvmTest\")").substringBefore("\n}\n")
        assertTrue("excludeTestsMatching(\"com.jamarglex.manijero.smoke.DesktopQaCheckRun\")" in jvmTest)
        assertTrue("tasks.register<Test>(\"runDesktopQaCheck\")" in sharedScript)
    }

    @Test
    fun `only runDesktopQaCheck references the generated token folder`() {
        val start = sharedScript.indexOf("tasks.register<Test>(\"runDesktopQaCheck\") {")
        assertTrue(start >= 0)
        val block = bracedBlock(sharedScript, sharedScript.indexOf('{', start))
        val outside = sharedScript.removeRange(start, start + block.length + 2 + "tasks.register<Test>(\"runDesktopQaCheck\") ".length)

        assertTrue("generated/pilotToken" in block && ":desktopApp:generatePilotTokenResource" in block)
        // The folders join the classpath when the task is configured: a doFirst append never reaches the forked JVM.
        assertTrue(Regex("""classpath = jvmTestTask\.get\(\)\.classpath \+ files\(environmentFolder, pilotTokenFolder\)""").containsMatchIn(block))
        assertTrue(":desktopApp:generateEnvironmentResource" in block)
        assertFalse("doFirst" in block)
        // Outside the task, the build script mentions neither the folder nor the generator.
        listOf("generated/pilotToken", "generatePilotTokenResource", "pilot-token.txt", "qa-test-device", "MANIJERO_PILOT_TOKEN_FILE").forEach {
            assertFalse(it in outside, "\"$it\" must stay inside runDesktopQaCheck")
        }
    }

    @Test
    fun `the qa check task sets no token property, environment entry, or argument`() {
        val start = sharedScript.indexOf("tasks.register<Test>(\"runDesktopQaCheck\") {")
        val block = bracedBlock(sharedScript, sharedScript.indexOf('{', start))

        val systemProperties = Regex("""systemProperty\s*\(([^)]*)\)""").findAll(block).map { it.groupValues[1] }.toList()
        assertEquals(listOf("\"java.awt.headless\", \"true\""), systemProperties)
        assertFalse(Regex("""\benvironment\s*\(""").containsMatchIn(block))
        assertFalse("jvmArgs(" in block || "args(" in block || "setArgs" in block)
        val defines = Regex("""-D([A-Za-z.]+)=""").findAll(block).map { it.groupValues[1] }.toList()
        assertEquals(listOf("manijero.smoke.expected", "manijero.smoke.result"), defines)
    }

    @Test
    fun `no init tier and no other source runs or names the live qa check`() {
        val init = root.resolve("scripts/init.sh").readText()
        assertFalse("runDesktopQaCheck" in init, "init.sh reaches the check only through qa_check.py")
        assertFalse("DesktopQaCheckRun" in init)
        val fast = init.substringAfter("run_fast() {").substringBefore("\n}\n")
        assertFalse("qa-check" in fast || "qa_check.py" in fast, "--fast must not start the QA check")
        val script = root.resolve("backend/app/qa_check.py").readText()
        assertTrue(":shared:runDesktopQaCheck" in script)
        assertFalse(Regex("""open\(|read_text\(|read_bytes\(""").containsMatchIn(script.substringAfter("def _check_prerequisites").substringBefore("def _shown")))
    }

    /** The text between the `{` at [openIndex] and its matching `}`, both excluded. */
    private fun bracedBlock(text: String, openIndex: Int): String {
        require(text[openIndex] == '{') { "expected '{' at $openIndex" }
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
