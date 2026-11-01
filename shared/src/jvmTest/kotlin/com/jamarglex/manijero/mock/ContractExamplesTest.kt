package com.jamarglex.manijero.mock

import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.answerJson
import kotlinx.serialization.json.Json
import java.io.File
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ContractExamplesTest {
    private val temporaryDirectories = mutableListOf<File>()

    @AfterTest
    fun deleteTemporaryDirectories() {
        temporaryDirectories.forEach { it.deleteRecursively() }
    }

    @Test
    fun `loads the three committed examples unchanged`() {
        val directory = contractExamplesDirectory()
        val examples = loadContractExamples(directory)

        assertEquals(AnswerStatus.answered, examples.answered.response.status)
        assertEquals(AnswerStatus.abstained, examples.abstained.response.status)
        assertEquals(AnswerStatus.needs_land_clarification, examples.clarification.response.status)
        listOf(examples.answered, examples.abstained, examples.clarification).forEach { served ->
            assertEquals(
                Json.parseToJsonElement(File(directory, served.fileName).readText()),
                Json.parseToJsonElement(answerJson.encodeToString(AskResponse.serializer(), served.response)),
            )
        }
    }

    @Test
    fun `a missing example fails closed naming only that file`() {
        val directory = copyOfExamples()
        File(directory, ABSTAINED_EXAMPLE_FILE).delete()

        val failure = assertFailsWith<ContractExampleException> { loadContractExamples(directory) }

        assertEquals(ABSTAINED_EXAMPLE_FILE, failure.fileName)
        assertEquals("the example file contracts/examples/$ABSTAINED_EXAMPLE_FILE is missing.", failure.message)
        assertFalse(failure.message.orEmpty().contains(directory.absolutePath))
    }

    @Test
    fun `an example with an unknown key fails closed naming that file`() {
        val directory = copyOfExamples()
        val file = File(directory, CLARIFICATION_EXAMPLE_FILE)
        file.writeText(file.readText().replaceFirst("{", """{"unexpected": "secreto","""))

        val failure = assertFailsWith<ContractExampleException> { loadContractExamples(directory) }

        assertEquals(CLARIFICATION_EXAMPLE_FILE, failure.fileName)
        assertTrue(failure.message.orEmpty().contains("contracts/examples/$CLARIFICATION_EXAMPLE_FILE"))
        assertFalse(failure.message.orEmpty().contains("secreto"))
    }

    @Test
    fun `an example that is not JSON fails closed naming that file`() {
        val directory = copyOfExamples()
        File(directory, ANSWERED_EXAMPLE_FILE).writeText("not json")

        val failure = assertFailsWith<ContractExampleException> { loadContractExamples(directory) }

        assertEquals(ANSWERED_EXAMPLE_FILE, failure.fileName)
    }

    private fun copyOfExamples(): File {
        val target = Files.createTempDirectory("mock-examples").toFile().also(temporaryDirectories::add)
        contractExamplesDirectory().listFiles().orEmpty().forEach { it.copyTo(File(target, it.name)) }
        return target
    }
}

/** Finds the committed `contracts/examples` directory from the Gradle test working directory. */
internal fun contractExamplesDirectory(): File {
    var directory: File? = File("").absoluteFile
    while (directory != null) {
        val candidate = File(directory, "contracts/examples")
        if (candidate.isDirectory) return candidate
        directory = directory.parentFile
    }
    error("Could not locate contracts/examples from ${File("").absolutePath}")
}
