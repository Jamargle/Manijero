package com.jamarglex.manijero.platform

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Repo-level guard for the local smoke test (`local_end_to_end_smoke`): the live Desktop check never
 * runs in an ordinary tier, the Android release source set gains nothing, and `ChatTestTags` stay
 * invisible tags that no product logic reads. It reads checked-in files only.
 */
class LocalSmokeGuardTest {
    private val root = repositoryRoot()

    @Test
    fun `the live desktop check is excluded from jvmTest and runs only through its own task`() {
        val script = root.resolve("shared/build.gradle.kts").readText()
        val jvmTest = script.substringAfter("tasks.named<Test>(\"jvmTest\")").substringBefore("\n}\n")
        assertTrue(
            "excludeTestsMatching(\"com.jamarglex.manijero.smoke.DesktopLocalSmokeRun\")" in jvmTest,
            "jvmTest must exclude the live smoke check",
        )
        assertTrue("tasks.register<Test>(\"runDesktopLocalSmoke\")" in script)
    }

    @Test
    fun `no init tier runs the live checks`() {
        val init = root.resolve("scripts/init.sh").readText()
        assertFalse("runDesktopLocalSmoke" in init, "init.sh reaches the Desktop check only through local_smoke.py")
        assertFalse("connectedAndroidTest" in init, "connectedAndroidTest uninstalls the app and its data")
        val fast = init.substringAfter("run_fast() {").substringBefore("\n}\n")
        assertFalse("local-smoke" in fast || "local_rag.py" in fast, "--fast must not start the smoke test")
    }

    @Test
    fun `the android release source set holds only the null tools`() {
        val release = root.resolve("androidApp/src/release")
        val files = release.walkTopDown().filter { it.isFile }.map { it.relativeTo(release).path }.toList()
        assertEquals(listOf("kotlin/com/jamarglex/manijero/TestBuildTools.kt"), files)
        assertFalse("smoke" in release.resolve(files.single()).readText().lowercase())
    }

    @Test
    fun `chat test tags are only ever passed to Modifier testTag`() {
        val sources = listOf(
            "shared/src/commonMain",
            "shared/src/androidMain",
            "shared/src/jvmMain",
            "shared/src/iosMain",
            "androidApp/src/main",
            "androidApp/src/debug",
            "androidApp/src/release",
            "desktopApp/src/main",
        ).map(root::resolve).filter(File::isDirectory)
        val use = Regex("""ChatTestTags\.[A-Z_]+""")
        val allowed = Regex("""\.testTag\(ChatTestTags\.[A-Z_]+\)""")
        val offenders = sources.flatMap { directory ->
            directory.walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "ChatTestTags.kt" }
                .flatMap { file ->
                    file.readLines().withIndex().filter { (_, line) ->
                        use.findAll(line).count() != allowed.findAll(line).count()
                    }.map { (index, line) -> "${file.relativeTo(root)}:${index + 1}: ${line.trim()}" }
                }
                .toList()
        }
        assertEquals(emptyList(), offenders)
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
