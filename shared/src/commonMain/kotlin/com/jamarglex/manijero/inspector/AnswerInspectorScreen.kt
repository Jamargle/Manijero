package com.jamarglex.manijero.inspector

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.design.ManijeroScreen
import com.jamarglex.manijero.design.ManijeroSectionHeader
import com.jamarglex.manijero.theme.ManijeroSpacing
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.inspector_back
import manijero.shared.generated.resources.inspector_claim_markers
import manijero.shared.generated.resources.inspector_claim_passed
import manijero.shared.generated.resources.inspector_claim_title
import manijero.shared.generated.resources.inspector_draft_duration
import manijero.shared.generated.resources.inspector_draft_markers
import manijero.shared.generated.resources.inspector_draft_outcome
import manijero.shared.generated.resources.inspector_draft_provider
import manijero.shared.generated.resources.inspector_draft_status
import manijero.shared.generated.resources.inspector_field
import manijero.shared.generated.resources.inspector_ms
import manijero.shared.generated.resources.inspector_no
import manijero.shared.generated.resources.inspector_no_passages
import manijero.shared.generated.resources.inspector_none
import manijero.shared.generated.resources.inspector_not_run
import manijero.shared.generated.resources.inspector_note
import manijero.shared.generated.resources.inspector_passage_cited
import manijero.shared.generated.resources.inspector_passage_excerpt
import manijero.shared.generated.resources.inspector_passage_id
import manijero.shared.generated.resources.inspector_passage_lexical
import manijero.shared.generated.resources.inspector_passage_lexical_rank
import manijero.shared.generated.resources.inspector_passage_location
import manijero.shared.generated.resources.inspector_passage_no_value
import manijero.shared.generated.resources.inspector_passage_not_cited
import manijero.shared.generated.resources.inspector_passage_score
import manijero.shared.generated.resources.inspector_passage_source
import manijero.shared.generated.resources.inspector_passage_title
import manijero.shared.generated.resources.inspector_passage_vector
import manijero.shared.generated.resources.inspector_result_abstention
import manijero.shared.generated.resources.inspector_result_cited
import manijero.shared.generated.resources.inspector_result_generation
import manijero.shared.generated.resources.inspector_result_total
import manijero.shared.generated.resources.inspector_search_calls
import manijero.shared.generated.resources.inspector_search_duration
import manijero.shared.generated.resources.inspector_search_fallback
import manijero.shared.generated.resources.inspector_search_k
import manijero.shared.generated.resources.inspector_search_mode
import manijero.shared.generated.resources.inspector_search_vector
import manijero.shared.generated.resources.inspector_search_vector_used
import manijero.shared.generated.resources.inspector_section_drafting
import manijero.shared.generated.resources.inspector_section_passages
import manijero.shared.generated.resources.inspector_section_result
import manijero.shared.generated.resources.inspector_section_search
import manijero.shared.generated.resources.inspector_section_verification
import manijero.shared.generated.resources.inspector_title
import manijero.shared.generated.resources.inspector_verification_codes
import manijero.shared.generated.resources.inspector_verification_duration
import manijero.shared.generated.resources.inspector_verification_passed
import manijero.shared.generated.resources.inspector_yes
import org.jetbrains.compose.resources.stringResource
import kotlin.math.abs
import kotlin.math.roundToLong

/**
 * The read-only, development-only `Inspección de la respuesta` detail route for one answer. It
 * renders exactly the [inspection] it is given: the search, each passage with its scores, the
 * drafting, the verification codes, and the result. State is written as text (for example
 * `Comprobación superada: sí`); there is no success colour, check mark, or confident treatment, and
 * nothing here is stored, copied, logged, or shared.
 */
@Composable
internal fun AnswerInspectorScreen(
    inspection: AnswerInspection,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ManijeroScreen(modifier = modifier) {
        Text(
            text = stringResource(Res.string.inspector_title),
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.semantics { heading() },
        )
        Text(
            text = stringResource(Res.string.inspector_note),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        SearchSection(inspection.retrieval)
        PassagesSection(inspection.retrieval?.passages.orEmpty())
        DraftingSection(inspection.drafting)
        VerificationSection(inspection.verification)
        ResultSection(inspection)
        TextButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(Res.string.inspector_back))
        }
    }
}

@Composable
private fun SearchSection(retrieval: InspectionRetrieval?) {
    ManijeroSectionHeader(title = stringResource(Res.string.inspector_section_search))
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        if (retrieval == null) {
            NotRun()
            return@ManijeroCard
        }
        Field(Res.string.inspector_search_mode, retrieval.mode)
        Field(Res.string.inspector_search_k, retrieval.k.toString())
        Field(Res.string.inspector_search_calls, retrieval.search_calls.toString())
        Field(Res.string.inspector_search_duration, millis(retrieval.duration_ms))
        val vector = retrieval.vector
        if (vector == null) {
            Field(Res.string.inspector_search_vector, stringResource(Res.string.inspector_not_run))
        } else {
            Field(Res.string.inspector_search_vector_used, yesNo(vector.used))
            vector.fallback_code?.let { Field(Res.string.inspector_search_fallback, it) }
        }
    }
}

@Composable
private fun PassagesSection(passages: List<InspectionPassage>) {
    ManijeroSectionHeader(title = stringResource(Res.string.inspector_section_passages))
    if (passages.isEmpty()) {
        Text(
            text = stringResource(Res.string.inspector_no_passages),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
        return
    }
    Column(verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small)) {
        passages.forEach { passage -> PassageCard(passage) }
    }
}

@Composable
private fun PassageCard(passage: InspectionPassage) {
    val noValue = stringResource(Res.string.inspector_passage_no_value)
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        Text(
            text = stringResource(Res.string.inspector_passage_title, passage.rank.toString(), passage.title),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Field(Res.string.inspector_passage_location, passage.location)
        Field(Res.string.inspector_passage_id, passage.passage_id)
        Field(Res.string.inspector_passage_source, passage.source_id)
        Field(Res.string.inspector_passage_score, decimal(passage.score))
        Field(Res.string.inspector_passage_lexical_rank, passage.lexical_rank?.toString() ?: noValue)
        Field(Res.string.inspector_passage_lexical, passage.lexical_score?.let(::decimal) ?: noValue)
        Field(Res.string.inspector_passage_vector, passage.vector_similarity?.let(::decimal) ?: noValue)
        Text(
            text = stringResource(
                if (passage.cited) Res.string.inspector_passage_cited else Res.string.inspector_passage_not_cited,
            ),
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Field(Res.string.inspector_passage_excerpt, passage.excerpt)
    }
}

@Composable
private fun DraftingSection(drafting: InspectionDrafting?) {
    ManijeroSectionHeader(title = stringResource(Res.string.inspector_section_drafting))
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        if (drafting == null) {
            NotRun()
            return@ManijeroCard
        }
        Field(Res.string.inspector_draft_provider, drafting.provider ?: noneText())
        Field(Res.string.inspector_draft_outcome, drafting.outcome ?: noneText())
        Field(Res.string.inspector_draft_status, drafting.status ?: noneText())
        Field(Res.string.inspector_draft_markers, drafting.cited_markers.joinOrNone())
        drafting.duration_ms?.let { Field(Res.string.inspector_draft_duration, millis(it)) }
    }
}

@Composable
private fun VerificationSection(verification: InspectionVerification?) {
    ManijeroSectionHeader(title = stringResource(Res.string.inspector_section_verification))
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        if (verification == null) {
            NotRun()
            return@ManijeroCard
        }
        Field(Res.string.inspector_verification_passed, yesNo(verification.ok))
        Field(Res.string.inspector_verification_codes, verification.issues.joinOrNone())
        verification.duration_ms?.let { Field(Res.string.inspector_verification_duration, millis(it)) }
    }
    verification?.claims?.forEach { claim ->
        ManijeroCard(tone = ManijeroCardTone.Outlined) {
            Text(
                text = stringResource(Res.string.inspector_claim_title, claim.index.toString()),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Field(Res.string.inspector_claim_passed, yesNo(claim.ok))
            Field(Res.string.inspector_claim_markers, claim.markers.joinOrNone())
            Field(Res.string.inspector_verification_codes, claim.issues.joinOrNone())
        }
    }
}

@Composable
private fun ResultSection(inspection: AnswerInspection) {
    ManijeroSectionHeader(title = stringResource(Res.string.inspector_section_result))
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        val outcome = inspection.outcome
        Field(Res.string.inspector_result_abstention, outcome.abstention_reason ?: noneText())
        Field(Res.string.inspector_result_generation, outcome.generation_reason ?: noneText())
        Field(Res.string.inspector_result_cited, outcome.cited_passage_ids.joinOrNone())
        Field(Res.string.inspector_result_total, millis(inspection.total_ms))
    }
}

@Composable
private fun NotRun() {
    Text(
        text = stringResource(Res.string.inspector_not_run),
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

/** One `label: value` line; the value is shown verbatim so codes can be read exactly. */
@Composable
private fun Field(label: org.jetbrains.compose.resources.StringResource, value: String) {
    Text(
        text = stringResource(Res.string.inspector_field, stringResource(label), value),
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
}

@Composable
private fun yesNo(value: Boolean): String =
    stringResource(if (value) Res.string.inspector_yes else Res.string.inspector_no)

@Composable
private fun noneText(): String = stringResource(Res.string.inspector_none)

@Composable
private fun millis(value: Long): String = stringResource(Res.string.inspector_ms, value.toString())

@Composable
private fun <T> List<T>.joinOrNone(): String =
    if (isEmpty()) noneText() else joinToString(", ")

/** Three decimals without platform formatting, so every target prints the same digits. */
internal fun decimal(value: Double): String {
    val scaled = (abs(value) * 1000).roundToLong()
    val sign = if (value < 0 && scaled != 0L) "-" else ""
    val whole = scaled / 1000
    val fraction = (scaled % 1000).toString().padStart(3, '0')
    return "$sign$whole,$fraction"
}
