package com.jamarglex.manijero.platform

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Repo-level guard for `client_environment_builds`: the two build scripts keep the same environment
 * setting, messages, placeholder, and token paths; the QA branch never names the local token and the
 * local branch never names the QA key; no committed file holds a real QA host. It reads only
 * checked-in files, never a token or address file.
 */
class EnvironmentBuildGuardTest {
    private val root = repositoryRoot()
    private val android = root.resolve("androidApp/build.gradle.kts").readText()
    private val desktop = root.resolve("desktopApp/build.gradle.kts").readText()
    private val scripts = listOf(android, desktop)

    @Test
    fun `the address file is git-ignored`() {
        assertTrue("/qa-address.local" in root.resolve(".gitignore").readLines().map { it.trim() })
    }

    @Test
    fun `both scripts share the setting, messages, placeholder, and paths`() {
        scripts.forEach { script ->
            assertTrue("providers.gradleProperty(\"manijeroEnvironment\").orElse(\"local\")" in script)
            assertTrue("manijeroEnvironment must be local or qa; prod is not configured." in script)
            assertTrue("val qaPlaceholderAddress = \"https://qa.manijero.invalid\"" in script)
            assertTrue(
                "qa-address.local is not a valid QA address. Write one https:// address on one line, for example https://qa.example.org" in script,
            )
            assertTrue("The QA access key is not valid. Run ./scripts/init.sh --qa-settings-setup again." in script)
            assertTrue("providers.environmentVariable(\"MANIJERO_QA_ADDRESS_FILE\").orElse(\"qa-address.local\")" in script)
            assertTrue("providers.environmentVariable(\"MANIJERO_QA_HOME\").orElse(System.getProperty(\"user.home\") + \"/manijero/qa\")" in script)
            assertTrue("\"\$it/credentials/qa-test-device.token\"" in script)
        }
        // Every build configures both apps, so only androidApp prints the placeholder notice (once).
        assertTrue("The QA address is a placeholder (\$qaPlaceholderAddress) until the QA server is chosen; " in android)
        assertTrue("this app cannot reach QA yet." in android)
        assertFalse("logger." in desktop)
        val patterns = scripts.map { Regex("""val qaAddressPattern = Regex\((.*?)\n\)""", RegexOption.DOT_MATCHES_ALL).find(it)?.value }
        assertTrue(patterns[0] != null && patterns[0] == patterns[1], "the QA address pattern must be identical in both scripts")
    }

    @Test
    fun `the qa key is never the local file and the local branch never names the qa key`() {
        scripts.forEach { script ->
            val local = Regex("""val localPilotTokenFile[^\n]*\n(.*?)\n\)""", RegexOption.DOT_MATCHES_ALL).find(script)?.value
                ?: error("localPilotTokenFile is required")
            val qa = Regex("""val qaAccessKeyFile[^\n]*\n(.*?)\n\)\n""", RegexOption.DOT_MATCHES_ALL).find(script)?.value
                ?: error("qaAccessKeyFile is required")
            assertTrue("pilot-token.local" in local)
            assertFalse("qa-test-device" in local || "MANIJERO_QA_HOME" in local)
            assertFalse("pilot-token.local" in qa)
            assertTrue("val pilotTokenFile: Provider<RegularFile> = if (qaBuild) qaAccessKeyFile else localPilotTokenFile" in script)
            // The QA address file is only read inside the QA branch.
            val qaBranch = script.indexOf("val qaAskBaseUrl: String? = if (qaBuild) {")
            assertTrue(qaBranch >= 0)
            assertEquals(1, Regex("MANIJERO_QA_ADDRESS_FILE").findAll(script).count())
            assertTrue(script.indexOf("MANIJERO_QA_ADDRESS_FILE") > qaBranch)
        }
    }

    @Test
    fun `the environment resource is non-secret and the two environments are separate apps`() {
        assertTrue("generated/environment" in desktop)
        val resourceTask = Regex("""register\("generateEnvironmentResource"\) \{(.*?)\n\}""", RegexOption.DOT_MATCHES_ALL)
            .find(desktop)?.groupValues?.get(1) ?: error("generateEnvironmentResource is required")
        listOf("pilotToken", "tokenFile", "qaAccessKeyFile", "localPilotTokenFile", "pilot-token").forEach {
            assertFalse(it in resourceTask, "the environment resource must not touch the token ($it)")
        }
        assertTrue("if (qaBuild) applicationIdSuffix = \".qa\"" in android)
        assertTrue("if (qaBuild) \"Manijero QA\" else \"@string/app_name\"" in android)
        assertTrue("if (qaBuild) \"com.jamarglex.manijero.qa\" else \"com.jamarglex.manijero\"" in desktop)
        assertTrue("android:label=\"\${appLabel}\"" in root.resolve("androidApp/src/main/AndroidManifest.xml").readText())
    }

    @Test
    fun `init offers one named command per host and keeps the local modes`() {
        val init = root.resolve("scripts/init.sh").readText()
        assertTrue("--android-qa" in init && "--desktop-qa" in init)
        assertTrue("-PmanijeroEnvironment=qa" in init)
        assertTrue(Regex("""--android\)\s*\n\s*\./gradlew :androidApp:assembleDebug\n""").containsMatchIn(init))
        assertTrue(Regex("""--desktop\)\s*\n\s*\./gradlew :desktopApp:run\n""").containsMatchIn(init))
    }

    @Test
    fun `no committed file names a real qa host`() {
        val files = listOf(
            "androidApp/build.gradle.kts", "desktopApp/build.gradle.kts", "scripts/check-environment-build.sh",
            "shared/src/jvmMain/kotlin/com/jamarglex/manijero/platform/DesktopEnvironment.kt",
        )
        files.forEach { path ->
            val file = root.resolve(path)
            if (!file.isFile) return@forEach
            Regex("""https://([A-Za-z0-9.-]+)""").findAll(file.readText()).map { it.groupValues[1] }.forEach { host ->
                assertTrue(host == "qa.manijero.invalid" || host == "qa.example.org", "$path names a host: $host")
            }
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
