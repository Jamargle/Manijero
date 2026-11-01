package com.jamarglex.manijero.mock

import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.answerJson
import java.io.File

/** One committed contract example and the file it was read from, so logs can name the file only. */
data class ServedExample(val fileName: String, val response: AskResponse)

/** The three committed `/ask` response examples the mock answer service is allowed to serve. */
data class ContractExamples(
    val answered: ServedExample,
    val abstained: ServedExample,
    val clarification: ServedExample,
)

const val ANSWERED_EXAMPLE_FILE = "response-answered.json"
const val ABSTAINED_EXAMPLE_FILE = "response-abstained.json"
const val CLARIFICATION_EXAMPLE_FILE = "response-needs-land-clarification.json"

/**
 * A committed example could not be used. The message names only the file, in plain words, so the
 * start command can show it to the owner as is.
 */
class ContractExampleException(val fileName: String, message: String) : Exception(message)

/**
 * Reads the committed response examples from [directory] (normally `contracts/examples`) and
 * decodes each one with the app's own [answerJson] into [AskResponse]. Fails closed: the first
 * missing or undecodable file throws [ContractExampleException], so no partial service can run.
 */
fun loadContractExamples(directory: File): ContractExamples = ContractExamples(
    answered = loadExample(directory, ANSWERED_EXAMPLE_FILE),
    abstained = loadExample(directory, ABSTAINED_EXAMPLE_FILE),
    clarification = loadExample(directory, CLARIFICATION_EXAMPLE_FILE),
)

private fun loadExample(directory: File, fileName: String): ServedExample {
    val file = File(directory, fileName)
    val shownName = "contracts/examples/$fileName"
    if (!file.isFile) {
        throw ContractExampleException(fileName, "the example file $shownName is missing.")
    }
    val text = try {
        file.readText()
    } catch (_: Exception) {
        throw ContractExampleException(fileName, "the example file $shownName cannot be read.")
    }
    val response = try {
        answerJson.decodeFromString(AskResponse.serializer(), text)
    } catch (_: Exception) {
        throw ContractExampleException(
            fileName,
            "the example file $shownName does not match the answer format the apps expect.",
        )
    }
    return ServedExample(fileName, response)
}
