package com.jamarglex.manijero.connection

/**
 * The shared protocol of the local smoke test (`./scripts/init.sh --local-smoke`). Test-build
 * tooling only: the Desktop driver (shared jvmTest) and the Android driver (androidApp androidTest)
 * use it, and no product screen or release build reads it.
 *
 * Each driver reports exactly one [smokeResultLine]. It carries the outcome code, the source count,
 * where the address came from, and the address in use, and never the question, answer, or passage
 * text.
 */

/** The one fixed, in-scope, non-personal question. It is sent as a `general` question with no lands. */
const val LOCAL_SMOKE_QUESTION = "¿Qué es la solicitud única de la PAC?"

/** The first word of the one result line a driver reports. */
const val LOCAL_SMOKE_RESULT_PREFIX = "MANIJERO_SMOKE_RESULT"

/** How long a driver waits for a reply to appear after `Preguntar` (and again after `Reintentar`). */
const val LOCAL_SMOKE_REPLY_TIMEOUT_MILLIS = 90_000L

/** What one platform showed. Only [Answered] (with at least one source card) and [Abstained] pass. */
enum class SmokeOutcome(val code: String, val passes: Boolean) {
    Answered("answered", true),
    Abstained("abstained", true),
    AnsweredWithoutSources("answered_without_sources", false),
    LandClarification("land_clarification", false),
    Unreachable("unreachable", false),
    ServiceError("service_error", false),
    NotReady("not_ready", false),
    ReadyUnknown("ready_unknown", false),
    NotManijero("not_manijero", false),
    OtherAddress("other_address", false),
    NoAnswer("no_answer", false),
    Error("error", false),
}

/**
 * [SmokeOutcome.OtherAddress] when the address in use is not the platform's service address
 * [expected] (after the same normalization `Conexión` applies), else `null`. Either side being
 * unusable counts as a different address, so no request is ever sent to it.
 */
fun smokeAddressOutcome(inUse: String, expected: String): SmokeOutcome? {
    val current = normalizeServiceAddress(inUse) as? ServiceAddressInput.Valid
    val wanted = normalizeServiceAddress(expected) as? ServiceAddressInput.Valid
    return if (current != null && wanted != null && current.url == wanted.url) null else SmokeOutcome.OtherAddress
}

/** The outcome of the `Conexión` probe on the address in use; `null` when it is ready to answer. */
fun smokeOutcomeFor(result: ServiceCheckResult): SmokeOutcome? = when (result) {
    ServiceCheckResult.Ready -> null
    ServiceCheckResult.NotReady -> SmokeOutcome.NotReady
    ServiceCheckResult.ReadyUnknown -> SmokeOutcome.ReadyUnknown
    ServiceCheckResult.Unreachable -> SmokeOutcome.Unreachable
    ServiceCheckResult.NotManijero -> SmokeOutcome.NotManijero
}

/** What a driver saw on the assistant screen after asking, read from `ChatTestTags` only. */
data class SmokeScreen(
    val answered: Boolean = false,
    val sourceCards: Int = 0,
    val abstained: Boolean = false,
    val landClarification: Boolean = false,
    val unreachable: Boolean = false,
    val serviceError: Boolean = false,
) {
    /** Whether the app has shown a final state, so the driver can stop waiting. */
    val settled: Boolean get() = answered || abstained || landClarification || unreachable || serviceError
}

/** The outcome for a settled [screen]; [SmokeOutcome.NoAnswer] when nothing appeared in time. */
fun smokeOutcomeFor(screen: SmokeScreen): SmokeOutcome = when {
    screen.answered && screen.sourceCards > 0 -> SmokeOutcome.Answered
    screen.answered -> SmokeOutcome.AnsweredWithoutSources
    screen.abstained -> SmokeOutcome.Abstained
    screen.landClarification -> SmokeOutcome.LandClarification
    screen.serviceError -> SmokeOutcome.ServiceError
    screen.unreachable -> SmokeOutcome.Unreachable
    else -> SmokeOutcome.NoAnswer
}

/** One platform's report: the outcome, the source cards shown, and the address in use. */
data class SmokeReport(
    val outcome: SmokeOutcome,
    val sources: Int,
    val source: ServiceAddressSource,
    val url: String,
)

/**
 * The one result line: `MANIJERO_SMOKE_RESULT outcome=<code> sources=<n> address=<default|saved>
 * url=<address in use>`. An address that is not a usable service address is reported as `invalid`,
 * so the line can never carry spaces or other text.
 */
fun smokeResultLine(report: SmokeReport): String {
    val url = (normalizeServiceAddress(report.url) as? ServiceAddressInput.Valid)?.url ?: "invalid"
    val address = when (report.source) {
        ServiceAddressSource.Default -> "default"
        ServiceAddressSource.Saved -> "saved"
    }
    return "$LOCAL_SMOKE_RESULT_PREFIX outcome=${report.outcome.code} sources=${report.sources.coerceAtLeast(0)} " +
        "address=$address url=$url"
}

/**
 * Wraps a [ServiceAddressStore] so a smoke driver can read the saved address but never save or
 * clear it: both writes throw, which `ActiveServiceAddress` already treats as "refused".
 */
class ReadOnlyServiceAddressStore(private val delegate: ServiceAddressStore) : ServiceAddressStore {
    override fun load(): String? = delegate.load()

    override fun save(address: String): Unit = throw UnsupportedOperationException("read-only")

    override fun clear(): Unit = throw UnsupportedOperationException("read-only")
}
