package com.jamarglex.manijero.smoke

import androidx.compose.ui.test.ComposeTimeoutException
import androidx.compose.ui.test.ComposeUiTest
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import com.jamarglex.manijero.App
import com.jamarglex.manijero.chat.AnswerService
import com.jamarglex.manijero.chat.ChatTestTags
import com.jamarglex.manijero.connection.ConnectionTools
import com.jamarglex.manijero.connection.LOCAL_SMOKE_QUESTION
import com.jamarglex.manijero.connection.LOCAL_SMOKE_REPLY_TIMEOUT_MILLIS
import com.jamarglex.manijero.connection.SmokeOutcome
import com.jamarglex.manijero.connection.SmokeReport
import com.jamarglex.manijero.connection.SmokeScreen
import com.jamarglex.manijero.connection.smokeAddressOutcome
import com.jamarglex.manijero.connection.smokeOutcomeFor

/**
 * The Desktop smoke steps over the shared `App`, rendered offscreen by a Compose UI test:
 *
 * 1. compare the address in use with the platform's service address [expected] — a different one
 *    ends the check with no request sent;
 * 2. run the `Conexión` probe on it;
 * 3. render `App` with no land store, type [LOCAL_SMOKE_QUESTION], press `Preguntar`;
 * 4. wait up to [replyTimeoutMillis] for a final state, press `Reintentar` exactly once after an
 *    unreachable failure, then classify what is shown from `ChatTestTags` only.
 *
 * The address store inside [tools] must be read-only; this script never saves or clears it, never
 * opens the land store, and keeps no question or answer text.
 */
@OptIn(ExperimentalTestApi::class)
class SmokeUiScript(
    private val tools: ConnectionTools,
    private val answerService: AnswerService,
    private val expected: String,
    private val replyTimeoutMillis: Long = LOCAL_SMOKE_REPLY_TIMEOUT_MILLIS,
) {
    /** Steps 1 and 2: a final report when the app would not ask, else `null`. */
    suspend fun preflight(): SmokeReport? {
        val inUse = tools.address.current
        smokeAddressOutcome(inUse, expected)?.let { return report(it) }
        smokeOutcomeFor(tools.checker.check(inUse))?.let { return report(it) }
        return null
    }

    /** Steps 3 and 4, inside a Compose UI test. */
    fun ask(test: ComposeUiTest): SmokeReport {
        test.setContent {
            App(landRepository = null, answerService = answerService, connectionTools = tools)
        }
        test.onNodeWithTag(ChatTestTags.QUESTION_FIELD).performScrollTo().performTextInput(LOCAL_SMOKE_QUESTION)
        test.onNodeWithTag(ChatTestTags.ASK_BUTTON).performScrollTo().performClick()
        var screen = test.awaitSettled()
        if (screen.unreachable) {
            // The first question after a start can exceed the app's request bound while Ollama
            // loads the model, so exactly one retry is allowed.
            test.onNodeWithTag(ChatTestTags.RETRY).performScrollTo().performClick()
            screen = test.awaitSettled()
        }
        return report(smokeOutcomeFor(screen), screen.sourceCards)
    }

    private fun report(outcome: SmokeOutcome, sources: Int = 0) =
        SmokeReport(outcome, sources, tools.address.source, tools.address.current)

    private fun ComposeUiTest.awaitSettled(): SmokeScreen {
        try {
            waitUntil(timeoutMillis = replyTimeoutMillis) { readScreen().settled }
        } catch (_: ComposeTimeoutException) {
            // Nothing final appeared in time: classified as `no_answer` below.
        }
        return readScreen()
    }

    private fun ComposeUiTest.readScreen() = SmokeScreen(
        answered = count(ChatTestTags.ANSWERED) > 0,
        sourceCards = count(ChatTestTags.SOURCE_CARD),
        abstained = count(ChatTestTags.ABSTAINED) > 0,
        landClarification = count(ChatTestTags.LAND_CLARIFICATION) > 0,
        unreachable = count(ChatTestTags.FAILURE_UNREACHABLE) > 0,
        serviceError = count(ChatTestTags.FAILURE_SERVICE) > 0,
    )

    private fun ComposeUiTest.count(tag: String): Int =
        onAllNodesWithTag(tag, useUnmergedTree = true).fetchSemanticsNodes().size
}
