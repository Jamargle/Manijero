package com.jamarglex.manijero.lands

/**
 * The Spanish labels one search needs, resolved by the caller.
 *
 * The labels live in `strings.xml` as Compose `StringResource` values, which a non-composable
 * function may not read, so the screen resolves them once per composition and passes them in. This
 * keeps the pure layer free of resource reads and of copy. A missing entry resolves to an empty
 * label, which makes that attribute unsearchable rather than throwing.
 */
data class LandSearchLabels(
    val waterRegime: Map<WaterRegime, String>,
    val productionMethod: Map<ProductionMethod, String>,
    val variety: Map<LandVariety, String>,
)

/**
 * Folds [value] for searching: the locale-invariant lowercase form, then `á é í ó ú ü → a e i o u u`
 * and `ñ → n`. Uppercase forms are folded by the lowercase step, and only the lowercase map is
 * needed. Folding `ñ → n` is a deliberate convenience (approved with the plan), not a ranking rule.
 */
fun foldForSearch(value: String): String {
    val lowered = value.lowercase()
    if (lowered.none { it in ACCENTED_LETTERS }) return lowered

    return buildString(lowered.length) {
        lowered.forEach { character ->
            append(ACCENTED_LETTERS[character] ?: character)
        }
    }
}

/**
 * The lands of [lands] whose text matches [query], in the order received.
 *
 * Only text is matched: name, zone, municipality, the variety text (the custom `Otra` text for
 * [LandVariety.OTHER], otherwise its resolved label), the resolved water-regime label and the
 * resolved production-method label. The id, notes, timestamps, surface and tree count are never
 * searched, so a measure can never be mistaken for a name.
 *
 * The folded query is split into maximal runs of letters or digits, so punctuation and emoji only
 * separate words and are never matched literally. A land matches when every token appears in its
 * folded text, so word order does not matter. A query with no tokens (blank, spaces, punctuation
 * only, emoji only) returns [lands] unchanged: it behaves exactly like a blank query, and
 * [hasSearchTokens] reports that same case for callers that must not describe it as a search.
 */
fun filterLands(lands: List<Land>, query: String, labels: LandSearchLabels): List<Land> {
    val tokens = searchTokens(query)
    if (tokens.isEmpty()) return lands

    return lands.filter { land ->
        val searchable = searchableText(land, labels)
        tokens.all { token -> searchable.contains(token) }
    }
}

/**
 * Whether [query] is a search that filters the list, i.e. whether it contains at least one
 * letter or digit.
 *
 * This is the single rule that decides it: [filterLands] returns the input list for a query with no
 * tokens, so any screen that states a filtered scope or a filtered caption MUST ask this predicate
 * instead of testing the raw text. Blank, spaces, punctuation only and emoji only are not a search,
 * and a `isNotBlank()` test would disagree with the filter for `...`, `¿?` or `😀`.
 */
fun hasSearchTokens(query: String): Boolean = searchTokens(query).isNotEmpty()

/** Every letter/digit run of the folded query, in order. */
private fun searchTokens(query: String): List<String> {
    val folded = foldForSearch(query)
    val tokens = mutableListOf<String>()
    val current = StringBuilder()
    folded.forEach { character ->
        if (character.isLetterOrDigit()) {
            current.append(character)
        } else if (current.isNotEmpty()) {
            tokens += current.toString()
            current.clear()
        }
    }
    if (current.isNotEmpty()) tokens += current.toString()
    return tokens
}

/** The folded text one land can be found by. Nothing else is searchable. */
private fun searchableText(land: Land, labels: LandSearchLabels): String {
    val varietyText = if (land.variety == LandVariety.OTHER) {
        land.varietyOther?.takeIf { it.isNotBlank() }.orEmpty()
    } else {
        labels.variety[land.variety].orEmpty()
    }

    val text = buildString {
        append(land.name)
        append(' ')
        append(land.zone)
        append(' ')
        land.municipality?.takeIf { it.isNotBlank() }?.let { municipality ->
            append(municipality)
            append(' ')
        }
        append(varietyText)
        append(' ')
        append(labels.waterRegime[land.waterRegime].orEmpty())
        append(' ')
        append(labels.productionMethod[land.productionMethod].orEmpty())
    }
    return foldForSearch(text)
}

private val ACCENTED_LETTERS: Map<Char, Char> = mapOf(
    'á' to 'a',
    'é' to 'e',
    'í' to 'i',
    'ó' to 'o',
    'ú' to 'u',
    'ü' to 'u',
    'ñ' to 'n',
)
