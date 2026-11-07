package com.jamarglex.manijero.smoke

import com.jamarglex.manijero.connection.ServiceAddressInput
import com.jamarglex.manijero.connection.ServiceAddressSource
import com.jamarglex.manijero.connection.SmokeReport
import com.jamarglex.manijero.connection.normalizeServiceAddress

/**
 * The result protocol of the QA Desktop check (`./scripts/init.sh --qa-check`). Test-build tooling
 * only: the live driver [DesktopQaCheckRun] writes exactly one result line, and
 * `backend/app/qa_check.py` parses it. The line carries codes, a source count, and the address,
 * never the question, answer, passage, or key text.
 */

/** The first word of the one result line. */
const val QA_CHECK_RESULT_PREFIX = "MANIJERO_QA_CHECK_RESULT"

/** How long the driver waits for the thanks or failure line after pressing `Útil`. */
const val QA_CHECK_FEEDBACK_TIMEOUT_MILLIS = 30_000L

/** What happened to the one `Útil` press. [NotTried] means no finished reply was shown. */
enum class FeedbackOutcome(val code: String) {
    Sent("sent"),
    Failed("failed"),
    NoReply("no_reply"),
    NotShown("not_shown"),
    NotTried("not_tried"),
}

/** Why the check could not start, before any question was sent. */
enum class QaCheckPrecondition(val code: String) {
    NotQaBuild("not_qa_build"),
    NoAccessKey("no_access_key"),
}

/** The result line of a run that did not start: it has no address or source of its own. */
fun qaCheckNotRunLine(precondition: QaCheckPrecondition): String =
    "$QA_CHECK_RESULT_PREFIX outcome=${precondition.code} sources=0 feedback=${FeedbackOutcome.NotTried.code} " +
        "address=default url=invalid"

/**
 * `MANIJERO_QA_CHECK_RESULT outcome=<code> sources=<n> feedback=<code> address=<default|saved>
 * url=<address in use>`. An address that is not a usable service address is reported as `invalid`.
 */
fun qaCheckResultLine(report: SmokeReport, feedback: FeedbackOutcome): String {
    val url = (normalizeServiceAddress(report.url) as? ServiceAddressInput.Valid)?.url ?: "invalid"
    val address = when (report.source) {
        ServiceAddressSource.Default -> "default"
        ServiceAddressSource.Saved -> "saved"
    }
    return "$QA_CHECK_RESULT_PREFIX outcome=${report.outcome.code} sources=${report.sources.coerceAtLeast(0)} " +
        "feedback=${feedback.code} address=$address url=$url"
}
