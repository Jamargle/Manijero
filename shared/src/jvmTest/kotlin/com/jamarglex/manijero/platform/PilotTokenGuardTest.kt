package com.jamarglex.manijero.platform

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Repo-level guard for the pilot token rules (`client_pilot_credentials`): the token comes only
 * from the git-ignored `pilot-token.local` (or the `MANIJERO_PILOT_TOKEN_FILE` override), never from
 * `local.properties`; it never becomes a Desktop JVM property, environment entry, or `jvmArgs`
 * value; no client source set installs a Ktor logging plugin; and every Android variant and both
 * service branches on each host receive it. It reads only checked-in files, never a token file.
 */
class PilotTokenGuardTest {
    private val root = repositoryRoot()
    private val androidScript = root.resolve("androidApp/build.gradle.kts").readText()
    private val desktopScript = root.resolve("desktopApp/build.gradle.kts").readText()

    @Test
    fun `the token file is git-ignored at the repository root`() {
        val lines = root.resolve(".gitignore").readLines().map { it.trim() }
        assertTrue("/pilot-token.local" in lines, ".gitignore must list /pilot-token.local")
    }

    @Test
    fun `no build script reads local properties and both read the token file or its override`() {
        val scripts = listOf("build.gradle.kts", "settings.gradle.kts", "shared/build.gradle.kts")
            .map { root.resolve(it).readText() } + androidScript + desktopScript
        scripts.forEach { assertFalse("local.properties" in it, "no build script may read local.properties") }
        listOf(androidScript, desktopScript).forEach { script ->
            assertTrue("providers.environmentVariable(\"MANIJERO_PILOT_TOKEN_FILE\")" in script)
            assertTrue(".orElse(\"pilot-token.local\")" in script)
            assertTrue(
                "pilot-token.local is not a valid pilot token. Run ./scripts/init.sh --pilot-token-save again." in script,
            )
        }
    }

    @Test
    fun `the desktop token never rides on a JVM property, environment entry, jvmArgs, or task property`() {
        assertFalse("jvmArgs" in desktopScript)
        assertFalse(Regex("""\benvironment\s*\(""").containsMatchIn(desktopScript))
        assertFalse("inputs.property" in desktopScript, "the token value must never be a task input property")
        val systemProperties = Regex("""systemProperty\s*\(([^)]*)\)""").findAll(desktopScript).map { it.groupValues[1] }.toList()
        assertEquals(listOf("\"manijero.testBuild\", \"true\""), systemProperties)
        assertTrue("resources.srcDir(generatePilotTokenResource)" in desktopScript)
    }

    @Test
    fun `every android variant gets the PILOT_TOKEN field`() {
        assertTrue(Regex("""onVariants\s*\{[^}]*buildConfigFields\??\.put\(\s*"PILOT_TOKEN"""").containsMatchIn(androidScript))
        assertFalse("onVariants(selector()" in androidScript, "the field must not be limited to some variants")
        assertEquals(1, Regex("\"PILOT_TOKEN\"").findAll(androidScript).count())
    }

    @Test
    fun `both service branches on each host receive the token`() {
        listOf(
            "androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt",
            "desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt",
        ).forEach { path ->
            val text = root.resolve(path).readText()
            val constructions = Regex("""KtorAnswerService\(([^)]*)\)""").findAll(text).map { it.groupValues[1] }.toList()
            assertEquals(2, constructions.size, "$path builds the answer service in two branches")
            constructions.forEach { assertTrue(it.trimEnd().endsWith("pilotToken"), "$path: $it must pass pilotToken") }
        }
        assertTrue("PilotToken.fromBuildSetting(BuildConfig.PILOT_TOKEN)" in root.resolve(
            "androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt",
        ).readText())
    }

    @Test
    fun `no client source set installs a ktor logging plugin`() {
        val clientSources = listOf(
            "shared/src/commonMain", "shared/src/jvmMain", "shared/src/androidMain", "shared/src/iosMain",
            "androidApp/src", "desktopApp/src",
        ).map { root.resolve(it) }.filter { it.isDirectory }
        val offenders = clientSources.flatMap { dir ->
            dir.walkTopDown().filter { it.isFile && it.extension == "kt" }
                .filter { "io.ktor.client.plugins.logging" in it.readText() }
                .toList()
        }
        assertEquals(emptyList(), offenders)
        listOf(androidScript, desktopScript, root.resolve("shared/build.gradle.kts").readText()).forEach {
            assertFalse("ktor.client.logging" in it, "no client logging dependency")
        }
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
