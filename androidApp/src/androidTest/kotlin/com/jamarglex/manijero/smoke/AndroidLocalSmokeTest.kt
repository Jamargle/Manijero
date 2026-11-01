package com.jamarglex.manijero.smoke

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.compose.ui.test.ComposeTimeoutException
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.jamarglex.manijero.App
import com.jamarglex.manijero.BuildConfig
import com.jamarglex.manijero.chat.ChatTestTags
import com.jamarglex.manijero.chat.KtorAnswerService
import com.jamarglex.manijero.chat.answerHttpClient
import com.jamarglex.manijero.connection.ActiveServiceAddress
import com.jamarglex.manijero.connection.AndroidServiceAddressStore
import com.jamarglex.manijero.connection.ConnectionTools
import com.jamarglex.manijero.connection.KtorServiceStatusChecker
import com.jamarglex.manijero.connection.LOCAL_SMOKE_QUESTION
import com.jamarglex.manijero.connection.LOCAL_SMOKE_REPLY_TIMEOUT_MILLIS
import com.jamarglex.manijero.connection.ReadOnlyServiceAddressStore
import com.jamarglex.manijero.connection.SmokeOutcome
import com.jamarglex.manijero.connection.SmokeReport
import com.jamarglex.manijero.connection.SmokeScreen
import com.jamarglex.manijero.connection.smokeAddressOutcome
import com.jamarglex.manijero.connection.smokeOutcomeFor
import com.jamarglex.manijero.connection.smokeResultLine
import com.jamarglex.manijero.platform.androidAskBaseUrl
import io.ktor.client.engine.android.Android
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** The instrumentation status key that carries the one smoke result line. */
private const val RESULT_STATUS_KEY = "manijero_smoke_result"

/** A status code of its own, so the line is never read as a test start, pass, or failure. */
private const val RESULT_STATUS_CODE = 2

/** The `am instrument -e` argument with the emulator's service address. */
private const val EXPECTED_ADDRESS_ARGUMENT = "expectedAddress"

/**
 * The Android emulator smoke check, run only by `./scripts/init.sh --local-smoke` through
 * `adb shell am instrument` (never `connectedAndroidTest`, which uninstalls the app and its data).
 *
 * It runs in the debug app's process with the debug wiring: the build-default address, the saved
 * `Conexión` address read through a read-only store, the Android answer client, and the `Conexión`
 * probe. It never opens the land store and never saves or clears an address. The steps are the
 * Desktop driver's (`shared/src/jvmTest/.../smoke/SmokeUiScript.kt`): address check, probe, ask the
 * fixed question, wait up to 90 s, retry once after an unreachable failure, classify from
 * `ChatTestTags`. It reports one result line as an instrumentation status and asserts a pass.
 */
@RunWith(AndroidJUnit4::class)
class AndroidLocalSmokeTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun askTheLocalAnswerService() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        if (Build.VERSION.SDK_INT >= 37) {
            instrumentation.uiAutomation.grantRuntimePermission(
                context.packageName,
                Manifest.permission.ACCESS_LOCAL_NETWORK,
            )
        }
        val expected = InstrumentationRegistry.getArguments().getString(EXPECTED_ADDRESS_ARGUMENT).orEmpty()

        val client = answerHttpClient(Android.create())
        val address = ActiveServiceAddress(
            androidAskBaseUrl(BuildConfig.ASK_BASE_URL),
            ReadOnlyServiceAddressStore(AndroidServiceAddressStore(context)),
        )
        val tools = ConnectionTools(address, KtorServiceStatusChecker(client))
        val answerService = KtorAnswerService(client, address::current)

        fun report(outcome: SmokeOutcome, sources: Int = 0) =
            SmokeReport(outcome, sources, address.source, address.current)

        val result = try {
            runBlocking {
                smokeAddressOutcome(address.current, expected)?.let { report(it) }
                    ?: smokeOutcomeFor(tools.checker.check(address.current))?.let { report(it) }
            } ?: run {
                compose.setContent {
                    App(landRepository = null, answerService = answerService, connectionTools = tools)
                }
                compose.onNodeWithTag(ChatTestTags.QUESTION_FIELD).performScrollTo().performTextInput(LOCAL_SMOKE_QUESTION)
                compose.onNodeWithTag(ChatTestTags.ASK_BUTTON).performScrollTo().performClick()
                var screen = compose.awaitSettled()
                if (screen.unreachable) {
                    compose.onNodeWithTag(ChatTestTags.RETRY).performScrollTo().performClick()
                    screen = compose.awaitSettled()
                }
                report(smokeOutcomeFor(screen), screen.sourceCards)
            }
        } catch (_: Exception) {
            // The exception may name the address or a body; only the outcome code is kept.
            report(SmokeOutcome.Error)
        } finally {
            client.close()
        }

        instrumentation.sendStatus(
            RESULT_STATUS_CODE,
            Bundle().apply { putString(RESULT_STATUS_KEY, smokeResultLine(result)) },
        )
        assertTrue("the smoke test did not pass: ${result.outcome.code}", result.outcome.passes)
    }

    private fun ComposeContentTestRule.awaitSettled(): SmokeScreen {
        try {
            waitUntil(timeoutMillis = LOCAL_SMOKE_REPLY_TIMEOUT_MILLIS) { readScreen().settled }
        } catch (_: ComposeTimeoutException) {
            // Nothing final appeared in time: classified as `no_answer`.
        }
        return readScreen()
    }

    private fun ComposeContentTestRule.readScreen() = SmokeScreen(
        answered = count(ChatTestTags.ANSWERED) > 0,
        sourceCards = count(ChatTestTags.SOURCE_CARD),
        abstained = count(ChatTestTags.ABSTAINED) > 0,
        landClarification = count(ChatTestTags.LAND_CLARIFICATION) > 0,
        unreachable = count(ChatTestTags.FAILURE_UNREACHABLE) > 0,
        serviceError = count(ChatTestTags.FAILURE_SERVICE) > 0,
    )

    private fun ComposeContentTestRule.count(tag: String): Int =
        onAllNodesWithTag(tag, useUnmergedTree = true).fetchSemanticsNodes().size
}
