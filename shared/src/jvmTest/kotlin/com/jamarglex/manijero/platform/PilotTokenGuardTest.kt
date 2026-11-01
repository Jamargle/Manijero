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
 * value; no client source set installs a Ktor logging plugin; only test builds carry it (owner
 * decision 5: the Android debug build type and the Desktop `run` task, never release or packaged
 * outputs); and both service branches on each host receive it. It reads only checked-in files,
 * never a token file.
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
    }

    @Test
    fun `only the desktop run task gets the generated token folder`() {
        val runStart = Regex("""tasks\.withType<JavaExec>\(\)\.matching \{ it\.name == "run" \}\.configureEach \{""")
            .find(desktopScript) ?: error("desktopApp/build.gradle.kts must configure the run task by name")
        val runBlock = bracedBlock(desktopScript, runStart.range.last)
        assertTrue("dependsOn(generatePilotTokenResource)" in runBlock)
        assertTrue("layout.buildDirectory.dir(\"generated/pilotToken\")" in runBlock)
        assertTrue(Regex("""doFirst \{ \(this as JavaExec\)\.classpath\(pilotTokenFolder\) \}""").containsMatchIn(runBlock))

        // Outside the run block the task name appears only at its registration, and the folder only
        // as that task's output: never a resource dir, dependency, file collection, or packaging input.
        val outsideRun = desktopScript.removeRange(runStart.range.first, runStart.range.last + runBlock.length + 2)
        assertEquals(
            listOf("val generatePilotTokenResource = tasks.register(\"generatePilotTokenResource\") {"),
            outsideRun.lines().map { it.trim() }.filter { "generatePilotTokenResource" in it },
        )
        assertEquals(1, Regex(Regex.escape("generated/pilotToken")).findAll(outsideRun).count())
        listOf("resources.srcDir", "runtimeOnly", "implementation(files", "files(generatePilotTokenResource", "pilotTokenFolder")
            .forEach { assertFalse(it in outsideRun, "\"$it\" must not carry the token outside the run task") }
    }

    @Test
    fun `only android debug reads the token file and release still declares a null field`() {
        val onVariants = Regex("""onVariants \{ variant ->""").find(androidScript) ?: error("androidComponents.onVariants is required")
        val variantsBlock = bracedBlock(androidScript, onVariants.range.first + "onVariants ".length)
        val debugStart = Regex("""if \(variant\.buildType == "debug"\) \{""").find(variantsBlock)
            ?: error("the file-backed field must be limited to the debug build type")
        val debugBlock = bracedBlock(variantsBlock, debugStart.range.last)
        val elseStart = Regex("""\}\s*else\s*\{""").find(variantsBlock, debugStart.range.last + debugBlock.length)
            ?: error("other build types need their own PILOT_TOKEN field")
        val elseBlock = bracedBlock(variantsBlock, elseStart.range.last)

        assertTrue("pilotTokenBuildConfigValue" in debugBlock)
        assertFalse("pilotTokenBuildConfigValue" in elseBlock)
        assertTrue("put(\"PILOT_TOKEN\", BuildConfigField(\"String\", \"null\", null))" in elseBlock)
        // Defined once, used once (under debug): no other path reads the token file.
        assertEquals(2, Regex("""\bpilotTokenBuildConfigValue\b""").findAll(androidScript).count())
        assertEquals(1, Regex("""\bpilotTokenFile\b\)""").findAll(androidScript).count())
        assertEquals(2, Regex("\"PILOT_TOKEN\"").findAll(androidScript).count())
        assertFalse(
            Regex("""buildConfigField\s*\(\s*"String"\s*,\s*"PILOT_TOKEN"""").containsMatchIn(androidScript),
            "a defaultConfig or buildTypes field would bypass the debug-only rule",
        )
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
