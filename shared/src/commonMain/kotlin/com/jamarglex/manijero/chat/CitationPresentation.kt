package com.jamarglex.manijero.chat

/**
 * Pure, Compose-free presentation layer for cited sources.
 *
 * It only reshapes decoded payload data: it never invents a source, excerpt, date, link, or claim,
 * it holds no state, and it performs no I/O. The UI calls it once per transcript entry during
 * composition.
 */

/** One rendered piece of an assistant reply body: verbatim text or a citation reference numeral. */
sealed interface AnswerSegment {
    data class Text(val text: String) : AnswerSegment
    data class Reference(val number: Int) : AnswerSegment
}

/**
 * One source rendered as a card. [number] is the reference number the reply's markers use, or
 * `null` when the reply's cited set does not line up with `sources` (fail closed: the client never
 * points at the wrong document). [verifiedOn] is the formatted verification date, or `null` only
 * when the decoded value is blank. [link] is an openable https URL, or `null`.
 */
data class SourceCard(
    val number: Int?,
    val title: String,
    val issuingBody: String,
    val location: String,
    val verifiedOn: String?,
    val excerpt: String,
    val link: String?,
)

data class AnswerSourcePresentation(val segments: List<AnswerSegment>, val cards: List<SourceCard>)

/** `[n]` citation token: one to three digits between square brackets. */
private val CITATION_MARKER = Regex("""\[(\d{1,3})]""")

/**
 * Renders one assistant reply.
 *
 * A reply is *conforming* only when its distinct canonical `[n]` markers are exactly `1..sources.size`
 * (the invariant `backend/app/generation.py` documents). A conforming reply turns each marker into a
 * [AnswerSegment.Reference] and numbers the cards by payload position, so reference `n` is card `n`.
 *
 * Anything else — a non-`answered` status, absent, sparse, out-of-range, non-numeric, or
 * leading-zero markers, or an unexpected `sources` set — fails closed: no marker is rewritten, no
 * card is numbered, and the single text segment is the reply body exactly as received. An
 * abstention therefore can never show a source, a reference, a figure, or a date even when a
 * malformed payload carries `sources`.
 */
fun answerSourcePresentation(
    status: AnswerStatus,
    answer: String,
    sources: List<AnswerSource>,
): AnswerSourcePresentation {
    if (status != AnswerStatus.answered) {
        return AnswerSourcePresentation(segments = listOf(AnswerSegment.Text(answer)), cards = emptyList())
    }

    val markers = CITATION_MARKER.findAll(answer).toList()
    // A token like `[007]` parses as 7 but is not byte-identical to `[7]`; treat any non-canonical
    // digit string as non-conforming so the text-fidelity invariant below can never be violated.
    val allCanonical = markers.all { it.value == "[${it.groupValues[1].toInt()}]" }
    val markerNumbers = markers.map { it.groupValues[1].toInt() }.toSet()
    val conforming = allCanonical && markerNumbers == (1..sources.size).toSet()

    val segments = if (!conforming) {
        listOf(AnswerSegment.Text(answer))
    } else {
        buildSegments(answer, markers)
    }

    val cards = sources.mapIndexed { index, source ->
        SourceCard(
            number = if (conforming) index + 1 else null,
            title = source.title,
            issuingBody = source.issuing_body,
            location = source.location,
            verifiedOn = formatVerificationDate(source.verified_on).takeIf { it.isNotBlank() },
            excerpt = source.excerpt,
            link = openableOfficialUrl(source.url),
        )
    }

    return AnswerSourcePresentation(segments = segments, cards = cards)
}

/**
 * Splits a conforming reply into text and references. Replacing each [AnswerSegment.Reference] with
 * `[n]` and concatenating the segments reproduces [answer] byte-for-byte.
 */
private fun buildSegments(answer: String, markers: List<MatchResult>): List<AnswerSegment> {
    val segments = mutableListOf<AnswerSegment>()
    var cursor = 0
    markers.forEach { match ->
        if (match.range.first > cursor) {
            segments += AnswerSegment.Text(answer.substring(cursor, match.range.first))
        }
        segments += AnswerSegment.Reference(match.groupValues[1].toInt())
        cursor = match.range.last + 1
    }
    // The trailing text is always appended (even when empty and there are no markers) so the
    // segments always reconstruct the whole answer.
    if (cursor < answer.length || segments.isEmpty()) {
        segments += AnswerSegment.Text(answer.substring(cursor))
    }
    return segments
}

/**
 * Returns [url] unchanged only when it is an openable official link: an `https://` URL (lowercase
 * scheme), with a non-blank host that contains a dot, and no whitespace or control character.
 * `http`, `javascript:`, `mailto:`, blank, hostless, or space-containing values return `null`.
 *
 * There is deliberately no client-side domain allowlist: approved official hosts are catalog policy
 * and duplicating them here would silently drift.
 */
fun openableOfficialUrl(url: String): String? {
    if (!url.startsWith("https://")) return null
    if (url.any { it.isWhitespace() || it.isISOControl() }) return null

    val afterScheme = url.removePrefix("https://")
    val authorityEnd = afterScheme.indexOfFirst { it == '/' || it == '?' || it == '#' }
    val authority = if (authorityEnd == -1) afterScheme else afterScheme.substring(0, authorityEnd)
    val host = authority.substringAfter('@').substringBefore(':')
    if (host.isBlank() || !host.contains('.')) return null

    return url
}

/**
 * Formats a strict `yyyy-MM-dd` date with a plausible month/day as `dd/MM/yyyy`. Any other shape is
 * returned unchanged: the client never invents or repairs a date. A blank value stays blank.
 */
fun formatVerificationDate(isoDate: String): String {
    if (isoDate.length != 10) return isoDate
    if (isoDate[4] != '-' || isoDate[7] != '-') return isoDate
    val year = isoDate.substring(0, 4)
    val month = isoDate.substring(5, 7)
    val day = isoDate.substring(8, 10)
    if (!year.all { it.isDigit() } || !month.all { it.isDigit() } || !day.all { it.isDigit() }) {
        return isoDate
    }
    val monthValue = month.toInt()
    val dayValue = day.toInt()
    if (monthValue !in 1..12 || dayValue !in 1..31) return isoDate
    return "$day/$month/$year"
}
