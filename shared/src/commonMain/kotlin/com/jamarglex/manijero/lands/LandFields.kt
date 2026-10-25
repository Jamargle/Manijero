package com.jamarglex.manijero.lands

import kotlin.math.abs
import kotlin.math.round

/** The longest accepted zone (paraje) text, after trimming. */
const val ZONE_MAX_LENGTH: Int = 80

/** The longest accepted custom variety text, after trimming. */
const val VARIETY_OTHER_MAX_LENGTH: Int = 40

/**
 * The approved variety selector order. It is a product decision from the approved UI-refresh plan,
 * not an inference: the list is fixed, and a new variety is a spec and copy change. `UNKNOWN` (`No lo
 * sé`) is deliberately last, after `Otra`, so the shortlist leads and the honest fallback closes it.
 */
val LAND_VARIETY_OPTIONS: List<LandVariety> = listOf(
    LandVariety.PICUAL,
    LandVariety.HOJIBLANCA,
    LandVariety.PICUDO,
    LandVariety.LECHIN_DE_SEVILLA,
    LandVariety.ARBEQUINA,
    LandVariety.MANZANILLA,
    LandVariety.GORDAL,
    LandVariety.MIXED,
    LandVariety.OTHER,
    LandVariety.UNKNOWN,
)

/** Why a zone value cannot be saved. */
enum class ZoneProblem { BLANK, TOO_LONG }

/**
 * The problem with a required zone, or `null` when it is acceptable. The check trims first, so a
 * field of only spaces is blank and a value with trailing spaces is not rejected for length.
 */
fun zoneProblem(raw: String): ZoneProblem? {
    val trimmed = raw.trim()
    return when {
        trimmed.isEmpty() -> ZoneProblem.BLANK
        trimmed.length > ZONE_MAX_LENGTH -> ZoneProblem.TOO_LONG
        else -> null
    }
}

/** Whether [raw] is a zone this app may save. */
fun isValidZone(raw: String): Boolean = zoneProblem(raw) == null

/**
 * Whether the custom variety text is acceptable for [variety]. The text is only required for
 * [LandVariety.OTHER]; every other choice may leave it blank because it is not stored at all.
 */
fun isValidVarietyOther(variety: LandVariety, raw: String): Boolean {
    if (variety != LandVariety.OTHER) return true
    val trimmed = raw.trim()
    return trimmed.isNotEmpty() && trimmed.length <= VARIETY_OTHER_MAX_LENGTH
}

/**
 * The custom variety text to keep, or `null`. It survives only for [LandVariety.OTHER], so switching
 * back to a shortlist variety never leaves stale free text in the record.
 */
fun normalizedVarietyOther(variety: LandVariety, raw: String?): String? =
    if (variety == LandVariety.OTHER) raw?.trim()?.ifEmpty { null } else null

/**
 * The outcome of parsing one optional measure field. A blank input is a valid "not provided" and
 * carries a `null` value; an invalid one carries nothing at all, so the raw text stays on screen for
 * correction and no guessed number can reach the store.
 */
sealed interface MeasureResult<out T> {
    /** The input was acceptable; the value is `null` when the person left it blank. */
    data class Valid<T>(val value: T?) : MeasureResult<T> {
        override fun valueOrNull(): T? = value
    }

    /** The input cannot be saved as a measure. */
    data object Invalid : MeasureResult<Nothing> {
        override fun valueOrNull(): Nothing? = null
    }

    val isValid: Boolean
        get() = this !== Invalid

    fun valueOrNull(): T?
}

/**
 * Parses the optional surface field as hectares. Blank is a valid absent value; a comma or a dot is
 * accepted as the decimal separator; letters, signs, several separators, non-finite values and
 * negative values are rejected. The accepted value is rounded to two decimals, so a longer entry is
 * kept at the stored precision instead of being refused as if the person had made a mistake.
 */
fun parseAreaHectares(raw: String): MeasureResult<Double> {
    val text = raw.trim()
    if (text.isEmpty()) return MeasureResult.Valid(null)

    val normalized = text.replace(',', '.')
    if (normalized.count { it == '.' } > 1) return MeasureResult.Invalid
    val parts = normalized.split('.')
    val whole = parts[0]
    val fraction = parts.getOrNull(1).orEmpty()
    if (whole.isEmpty() && fraction.isEmpty()) return MeasureResult.Invalid
    if (!whole.all { it.isAsciiDigit() } || !fraction.all { it.isAsciiDigit() }) {
        return MeasureResult.Invalid
    }

    val value = normalized.toDoubleOrNull() ?: return MeasureResult.Invalid
    if (!value.isFinite() || value < 0.0) return MeasureResult.Invalid
    return MeasureResult.Valid(roundHectares(value))
}

/**
 * Parses the optional olive-tree count. Blank is a valid absent value; only ASCII digits are
 * accepted, the number must fit in an [Int], and it must be at least one. A decimal, a sign, a
 * thousands separator and zero are rejected.
 */
fun parseTreeCount(raw: String): MeasureResult<Int> {
    val text = raw.trim()
    if (text.isEmpty()) return MeasureResult.Valid(null)
    if (!text.all { it.isAsciiDigit() }) return MeasureResult.Invalid
    val value = text.toIntOrNull() ?: return MeasureResult.Invalid
    if (value < 1) return MeasureResult.Invalid
    return MeasureResult.Valid(value)
}

/** Rounds a surface to at most two decimals, the precision the app stores. */
fun roundHectares(value: Double): Double {
    if (!value.isFinite()) return value
    // Beyond this magnitude the `* 100` itself would overflow to infinity, and the value has no
    // meaningful fractional part left anyway; returning it untouched keeps a finite value finite.
    if (abs(value) > Double.MAX_VALUE / 100.0) return value
    return round(value * 100.0) / 100.0
}

/**
 * Formats a stored surface for people: a decimal comma, at most two decimals, and no trailing zeros
 * (`1,5`, `2`, `0,75`). No unit is added here; the caller's copy owns it. Extremely large values keep
 * their plain machine form rather than overflowing the integer path.
 */
fun formatHectares(value: Double): String {
    if (!value.isFinite()) return value.toString()
    val rounded = roundHectares(value)
    if (abs(rounded) >= 1_000_000_000_000.0) return rounded.toString()

    val negative = rounded < 0.0
    val hundredths = round(abs(rounded) * 100.0).toLong()
    val whole = hundredths / 100
    val fraction = (hundredths % 100).toInt()
    val fractionText = when {
        fraction == 0 -> ""
        fraction % 10 == 0 -> ",${fraction / 10}"
        else -> ",${fraction.toString().padStart(2, '0')}"
    }
    return (if (negative) "-" else "") + whole.toString() + fractionText
}

/** The editable text for a stored surface: blank when absent, otherwise [formatHectares]. */
fun areaInputText(areaHectares: Double?): String =
    areaHectares?.let(::formatHectares).orEmpty()

/** Formats a tree count with a plain space as the thousands separator (`85`, `1 200`). */
fun formatTreeCount(count: Long): String {
    val text = count.toString()
    val negative = text.startsWith('-')
    val digits = if (negative) text.substring(1) else text
    val grouped = buildString {
        digits.forEachIndexed { index, character ->
            if (index > 0 && (digits.length - index) % 3 == 0) append(' ')
            append(character)
        }
    }
    return (if (negative) "-" else "") + grouped
}

/**
 * The same grouping for one land's stored count. Sums are formatted through the [Long] entry
 * point, so the app has one grouping implementation.
 */
fun formatTreeCount(count: Int): String = formatTreeCount(count.toLong())

private fun Char.isAsciiDigit(): Boolean = this in '0'..'9'
