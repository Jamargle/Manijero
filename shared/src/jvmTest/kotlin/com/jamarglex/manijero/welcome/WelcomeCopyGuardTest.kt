package com.jamarglex.manijero.welcome

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** The welcome copy summarizes accepted strings: every source exists and no new fact shape appears. */
class WelcomeCopyGuardTest {
    private val strings: Map<String, String> by lazy {
        val file = File(repositoryRoot(), "shared/src/commonMain/composeResources/values/strings.xml")
        val nodes = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file).getElementsByTagName("string")
        (0 until nodes.length).associate { index ->
            nodes.item(index).attributes.getNamedItem("name").nodeValue to nodes.item(index).textContent
        }
    }

    @Test
    fun everyWelcomeKeyAndSourceKeyExists() {
        WELCOME_COPY_SOURCES.forEach { (key, sources) ->
            assertTrue(key in strings, "missing $key")
            sources.forEach { source -> assertTrue(source in strings, "$key cites missing $source") }
        }
        assertTrue("welcome_dismiss" in strings && "coverage_show_welcome" in strings)
    }

    @Test
    fun welcomeStringsHaveNoDigitsPromisesOrCorrectnessClaims() {
        (WELCOME_COPY_SOURCES.keys + "welcome_dismiss" + "coverage_show_welcome").forEach { key ->
            val value = strings.getValue(key)
            assertFalse(value.any { it.isDigit() }, "$key has a digit")
            assertFalse("garantiz" in value.lowercase(), "$key promises")
            assertFalse("correct" in value.lowercase(), "$key claims correctness")
        }
    }

    private fun repositoryRoot(): File {
        var directory: File? = File("").absoluteFile
        while (directory != null) {
            if (File(directory, "androidApp/src/main/AndroidManifest.xml").isFile) return directory
            directory = directory.parentFile
        }
        error("Could not locate the repository root")
    }
}
