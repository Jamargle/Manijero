package com.jamarglex.manijero.smoke

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import com.jamarglex.manijero.chat.KtorAnswerService
import com.jamarglex.manijero.chat.answerHttpClient
import com.jamarglex.manijero.connection.ActiveServiceAddress
import com.jamarglex.manijero.connection.ConnectionTools
import com.jamarglex.manijero.connection.FileServiceAddressStore
import com.jamarglex.manijero.connection.KtorServiceStatusChecker
import com.jamarglex.manijero.connection.ReadOnlyServiceAddressStore
import com.jamarglex.manijero.connection.SmokeOutcome
import com.jamarglex.manijero.connection.SmokeReport
import com.jamarglex.manijero.connection.desktopConnectionStorePath
import com.jamarglex.manijero.connection.smokeResultLine
import com.jamarglex.manijero.platform.desktopAskBaseUrl
import io.ktor.client.engine.cio.CIO
import kotlinx.coroutines.runBlocking
import org.junit.Assume.assumeTrue
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.nio.file.StandardCopyOption
import kotlin.test.Test

/** Set by `:shared:runDesktopLocalSmoke` from `-PmanijeroSmokeExpected` and `-PmanijeroSmokeResult`. */
const val SMOKE_EXPECTED_PROPERTY = "manijero.smoke.expected"
const val SMOKE_RESULT_PROPERTY = "manijero.smoke.result"

/**
 * The live Desktop smoke check, run only by `:shared:runDesktopLocalSmoke` (which
 * `./scripts/init.sh --local-smoke` starts). It is excluded from `:shared:jvmTest` and skips itself
 * when the result property is absent, so no ordinary tier ever reaches the network.
 *
 * It uses the same wiring as the Desktop development app: the build-default address, the saved
 * `~/.manijero/connection-v1.txt` read-only, the real CIO answer client, and the `Conexión` probe.
 * It never opens the land store. Its only write is the one result line, replaced atomically.
 */
@OptIn(ExperimentalTestApi::class)
class DesktopLocalSmokeRun {
    @Test
    fun askTheLocalAnswerService() {
        val resultFile = System.getProperty(SMOKE_RESULT_PROPERTY)?.takeIf(String::isNotBlank)
        assumeTrue("only ./scripts/init.sh --local-smoke runs this check", resultFile != null)
        val expected = System.getProperty(SMOKE_EXPECTED_PROPERTY).orEmpty()

        val client = answerHttpClient(CIO.create())
        val address = ActiveServiceAddress(
            desktopAskBaseUrl(),
            ReadOnlyServiceAddressStore(FileServiceAddressStore(desktopConnectionStorePath())),
        )
        val tools = ConnectionTools(address, KtorServiceStatusChecker(client))
        val script = SmokeUiScript(tools, KtorAnswerService(client, address::current), expected)
        val report = try {
            runBlocking { script.preflight() } ?: run {
                var asked: SmokeReport? = null
                runDesktopComposeUiTest(width = 900, height = 1600) { asked = script.ask(this) }
                asked ?: SmokeReport(SmokeOutcome.Error, 0, address.source, address.current)
            }
        } catch (_: Exception) {
            // The exception may name the address or a body; only the outcome code is kept.
            SmokeReport(SmokeOutcome.Error, 0, address.source, address.current)
        } finally {
            client.close()
        }
        writeAtomically(Paths.get(resultFile!!), smokeResultLine(report) + "\n")
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
