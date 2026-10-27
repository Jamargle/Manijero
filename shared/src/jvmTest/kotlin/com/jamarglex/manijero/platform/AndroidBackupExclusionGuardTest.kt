package com.jamarglex.manijero.platform

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail
import org.w3c.dom.Document
import org.w3c.dom.Element

/**
 * Repo-level guard for the shipped promise that land data has no operating-system backup
 * destination.
 *
 * The Android app declares `android:allowBackup="true"` (other non-land app data may still be backed
 * up), so the exclusion has to live in the two platform rule files. This test fails if the manifest
 * stops pointing at them, if either rule file stops excluding the private preferences file that holds
 * the land aggregate and its automatic copies, or if a rule file starts including it again. It reads
 * the checked-in Android sources, so it is cheap and runs in the ordinary `:shared:jvmTest` fast
 * tier; it does not need an Android SDK, emulator, or device.
 */
class AndroidBackupExclusionGuardTest {

    @Test
    fun the_android_manifest_keeps_land_preferences_out_of_os_backup() {
        val repoRoot = repositoryRoot()
        val manifest = repoRoot.resolve("androidApp/src/main/AndroidManifest.xml")
        assertTrue(manifest.isFile, "missing Android manifest at $manifest")
        val application = applicationElement(parse(manifest), manifest)

        val landPreferences = landPreferencesFileName(repoRoot)

        // `android:allowBackup="false"` would exclude every app data domain outright, which also
        // satisfies the promise; with the default (true) the rule files below must do the work.
        val allowBackup = application.getAttribute("android:allowBackup")
        if (allowBackup == "false") return
        assertEquals(
            "true",
            allowBackup,
            "android:allowBackup must be declared explicitly as \"false\" or \"true\" in $manifest",
        )

        val backupRulesAttribute = application.getAttribute("android:fullBackupContent")
        val extractionRulesAttribute = application.getAttribute("android:dataExtractionRules")
        assertTrue(
            backupRulesAttribute.startsWith("@xml/"),
            "android:fullBackupContent must reference an @xml rule file, was \"$backupRulesAttribute\"",
        )
        assertTrue(
            extractionRulesAttribute.startsWith("@xml/"),
            "android:dataExtractionRules must reference an @xml rule file, was " +
                "\"$extractionRulesAttribute\"",
        )

        val backupRules = rulesDocument(repoRoot, backupRulesAttribute)
        assertEquals(
            "full-backup-content",
            backupRules.documentElement.tagName,
            "${backupRulesAttribute} is not a full-backup-content document",
        )
        assertExcluded(backupRules.documentElement, landPreferences, backupRulesAttribute)

        val extractionRules = rulesDocument(repoRoot, extractionRulesAttribute)
        assertEquals(
            "data-extraction-rules",
            extractionRules.documentElement.tagName,
            "${extractionRulesAttribute} is not a data-extraction-rules document",
        )
        for (section in listOf("cloud-backup", "device-transfer")) {
            val nodes = extractionRules.getElementsByTagName(section)
            assertEquals(
                1,
                nodes.length,
                "$extractionRulesAttribute must declare exactly one <$section> section",
            )
            assertExcluded(nodes.item(0) as Element, landPreferences, extractionRulesAttribute)
        }
    }

    /** Asserts [parent] excludes, and never includes, the land preferences file. */
    private fun assertExcluded(parent: Element, landPreferences: String, label: String) {
        val rules = parent.getElementsByTagName("*")
        val matching = (0 until rules.length)
            .map { rules.item(it) as Element }
            .filter { it.getAttribute("path") == landPreferences }
        assertTrue(
            matching.any { it.tagName == "exclude" && it.getAttribute("domain") == "sharedpref" },
            "$label must exclude domain=\"sharedpref\" path=\"$landPreferences\"",
        )
        assertTrue(
            matching.none { it.tagName == "include" },
            "$label must not include path=\"$landPreferences\"",
        )
    }

    /**
     * The private preferences file the Android land store actually writes, derived from the adapter
     * instead of a second copy of the literal, so renaming the store cannot silently outrun the
     * exclusion rules.
     */
    private fun landPreferencesFileName(repoRoot: File): String {
        val adapter = repoRoot.resolve(
            "shared/src/androidMain/kotlin/com/jamarglex/manijero/lands/AndroidLandStorage.kt",
        )
        assertTrue(adapter.isFile, "missing Android land store adapter at $adapter")
        val name = Regex("getSharedPreferences\\(\\s*\"([^\"]+)\"")
            .find(adapter.readText())
            ?.groupValues
            ?.get(1)
            ?: fail("could not read the land preferences file name from $adapter")
        return "$name.xml"
    }

    private fun rulesDocument(repoRoot: File, reference: String): Document {
        val name = reference.removePrefix("@xml/")
        val rules = repoRoot.resolve("androidApp/src/main/res/xml/$name.xml")
        assertTrue(rules.isFile, "$reference does not resolve to a checked-in rule file at $rules")
        return parse(rules)
    }

    private fun applicationElement(document: Document, manifest: File): Element {
        val elements = document.getElementsByTagName("application")
        assertEquals(1, elements.length, "$manifest must declare exactly one <application>")
        return elements.item(0) as Element
    }

    private fun parse(file: File): Document =
        DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file)

    private fun repositoryRoot(): File {
        var directory: File? = File("").absoluteFile
        while (directory != null) {
            if (File(directory, "androidApp/src/main/AndroidManifest.xml").isFile) return directory
            directory = directory.parentFile
        }
        error("Could not locate the repository root from ${File("").absolutePath}")
    }
}
