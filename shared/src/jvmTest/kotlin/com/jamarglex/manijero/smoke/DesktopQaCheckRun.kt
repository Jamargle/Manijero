package com.jamarglex.manijero.smoke

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import com.jamarglex.manijero.chat.KtorAnswerService
import com.jamarglex.manijero.chat.PilotToken
import com.jamarglex.manijero.chat.answerHttpClient
import com.jamarglex.manijero.connection.ActiveServiceAddress
import com.jamarglex.manijero.connection.ConnectionTools
import com.jamarglex.manijero.connection.FileServiceAddressStore
import com.jamarglex.manijero.connection.KtorServiceStatusChecker
import com.jamarglex.manijero.connection.LOCAL_SMOKE_REPLY_TIMEOUT_MILLIS
import com.jamarglex.manijero.connection.ReadOnlyServiceAddressStore
import com.jamarglex.manijero.connection.ServiceAddressStore
import com.jamarglex.manijero.connection.SmokeOutcome
import com.jamarglex.manijero.connection.SmokeReport
import com.jamarglex.manijero.connection.desktopConnectionStorePath
import com.jamarglex.manijero.platform.DesktopEnvironment
import com.jamarglex.manijero.platform.desktopEnvironment
import com.jamarglex.manijero.platform.desktopPilotToken
import io.ktor.client.HttpClient
import io.ktor.client.plugins.HttpSend
import io.ktor.client.plugins.plugin
import io.ktor.client.engine.cio.CIO
import kotlinx.coroutines.runBlocking
import org.junit.Assume.assumeTrue
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.nio.file.StandardCopyOption
import kotlin.test.Test

/**
 * The live QA Desktop check, run only by `:shared:runDesktopQaCheck` (which
 * `./scripts/init.sh --qa-check` starts). It is excluded from `:shared:jvmTest` and skips itself
 * when the result property is absent, so no ordinary tier ever reaches the network.
 *
 * It wires the shared app like the `Manijero QA` Desktop test build: the QA environment and access
 * key built in as classpath resources, the QA data folder's saved address read-only, the real CIO
 * answer client. It never opens the land store. Its only write is the one result line, replaced
 * atomically. The access key is read once through [desktopPilotToken] and only handed to the answer
 * client; it is never printed, logged, or written.
 */
@OptIn(ExperimentalTestApi::class)
class DesktopQaCheckRun {
    @Test
    fun checkTheQaService() {
        val resultFile = System.getProperty(SMOKE_RESULT_PROPERTY)?.takeIf(String::isNotBlank)
        assumeTrue("only ./scripts/init.sh --qa-check runs this check", resultFile != null)
        val expected = System.getProperty(SMOKE_EXPECTED_PROPERTY).orEmpty()

        val environment = try {
            desktopEnvironment()
        } catch (_: Exception) {
            DesktopEnvironment.Local
        }
        val client = answerHttpClient(CIO.create())
        val line = try {
            val folder = (environment as? DesktopEnvironment.Qa)?.dataFolder ?: DesktopEnvironment.Local.dataFolder
            qaCheckLine(
                environment,
                desktopPilotToken(),
                client,
                FileServiceAddressStore(desktopConnectionStorePath(folder = folder)),
                expected,
            )
        } finally {
            client.close()
        }
        writeAtomically(Paths.get(resultFile!!), line + "\n")
    }

    private fun writeAtomically(target: Path, text: String) {
        val absolute = target.toAbsolutePath()
        Files.createDirectories(absolute.parent)
        val temporary = Files.createTempFile(absolute.parent, "desktop-result", ".tmp")
        try {
            Files.writeString(temporary, text)
            Files.move(temporary, absolute, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
        } finally {
            Files.deleteIfExists(temporary)
        }
    }
}

/**
 * The one QA check result line for the app wired from [environment], [token], [client] and the
 * read-only [savedAddress] store: compare the address in use with [expected], probe `Conexión`, ask
 * the fixed synthetic question, and press `Útil` once when a reply (answer or abstention) was shown.
 * A QA-less environment or a missing access key ends the run before any request is sent.
 */
@OptIn(ExperimentalTestApi::class)
internal fun qaCheckLine(
    environment: DesktopEnvironment,
    token: PilotToken?,
    client: HttpClient,
    savedAddress: ServiceAddressStore,
    expected: String,
    replyTimeoutMillis: Long = LOCAL_SMOKE_REPLY_TIMEOUT_MILLIS,
    feedbackTimeoutMillis: Long = QA_CHECK_FEEDBACK_TIMEOUT_MILLIS,
): String {
    if (environment !is DesktopEnvironment.Qa) return qaCheckNotRunLine(QaCheckPrecondition.NotQaBuild)
    if (token == null) return qaCheckNotRunLine(QaCheckPrecondition.NoAccessKey)

    // The app maps every feedback failure to one payload-free signal, so the status of the one
    // /feedback call is noted here (the code only) to tell "QA has no feedback yet" (404) apart.
    val feedbackStatuses = java.util.Collections.synchronizedList(mutableListOf<Int>())
    client.plugin(HttpSend).intercept { request ->
        val call = execute(request)
        if (call.request.url.encodedPath.endsWith("/feedback")) feedbackStatuses += call.response.status.value
        call
    }
    val address = ActiveServiceAddress(environment.defaultAskBaseUrl(), ReadOnlyServiceAddressStore(savedAddress))
    val tools = ConnectionTools(address, KtorServiceStatusChecker(client))
    val answers = KtorAnswerService(client, address::current, pilotToken = token, acceptInspection = true)
    val script = SmokeUiScript(tools, answers, expected, replyTimeoutMillis, feedbackTimeoutMillis)
    return try {
        val early = runBlocking { script.preflight() }
        if (early != null) {
            qaCheckResultLine(early, FeedbackOutcome.NotTried)
        } else {
            var asked: SmokeReport? = null
            var feedback = FeedbackOutcome.NotTried
            runDesktopComposeUiTest(width = 900, height = 1600) {
                val report = script.ask(this)
                asked = report
                if (report.outcome in RATEABLE) feedback = script.rateUseful(this)
            }
            if (feedback == FeedbackOutcome.Failed && feedbackStatuses.singleOrNull() == 404) {
                feedback = FeedbackOutcome.NotOnQa
            }
            qaCheckResultLine(asked ?: errorReport(address), feedback)
        }
    } catch (_: Exception) {
        // The exception may name the address or a body; only the outcome code is kept.
        qaCheckResultLine(errorReport(address), FeedbackOutcome.NotTried)
    }
}

private val RATEABLE = setOf(SmokeOutcome.Answered, SmokeOutcome.AnsweredWithoutSources, SmokeOutcome.Abstained)

private fun errorReport(address: ActiveServiceAddress) =
    SmokeReport(SmokeOutcome.Error, 0, address.source, address.current)
