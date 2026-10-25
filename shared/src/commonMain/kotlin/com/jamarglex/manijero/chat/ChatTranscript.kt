package com.jamarglex.manijero.chat

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.BaselineShift
import androidx.compose.ui.text.withStyle
import com.jamarglex.manijero.ChatMessage
import com.jamarglex.manijero.Speaker
import com.jamarglex.manijero.design.ManijeroIcon
import com.jamarglex.manijero.theme.LocalManijeroSemanticColors
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroShapes
import com.jamarglex.manijero.theme.ManijeroSpacing
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.chat_answer_state_abstained
import manijero.shared.generated.resources.chat_land_scope_all_active
import manijero.shared.generated.resources.chat_land_scope_general
import manijero.shared.generated.resources.chat_land_scope_selected
import manijero.shared.generated.resources.chat_speaker_assistant
import manijero.shared.generated.resources.chat_speaker_you
import manijero.shared.generated.resources.ic_warning
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource

/**
 * One transcript entry in the order it arrived. A `Tú` entry is the person's own words: it sits at
 * the end of the column at most 85 % wide and keeps its written `Tú` label, so the alignment is a
 * visual cue only and the entry is never announced as a reply. An `Asistente` entry stays a calm
 * neutral card; an abstention keeps the caution pair and both of its labels.
 */
@Composable
internal fun ChatMessageBubble(message: ChatMessage, modifier: Modifier = Modifier) {
    when (message.speaker) {
        Speaker.USER -> Row(
            modifier = modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.End,
        ) {
            ChatBubble(
                modifier = Modifier.fillMaxWidth(0.85f),
                label = stringResource(Res.string.chat_speaker_you),
                labelColor = MaterialTheme.colorScheme.onPrimary,
                text = message.text,
                textColor = MaterialTheme.colorScheme.onPrimary,
                containerColor = MaterialTheme.colorScheme.primary,
                borderColor = null,
            )
        }

        Speaker.ASSISTANT -> when (message.answerStatus) {
            // A supported answer keeps the calm neutral card. The code-owned lead-in and orientative
            // notice are already inside the server `answer`, so no client label, disclaimer, badge,
            // or "verified" affordance is added: that would be the confident treatment to avoid.
            // When the reply cites sources, each `[n]` marker becomes a reference numeral and every
            // cited source is shown as a card below the answer.
            AnswerStatus.answered -> {
                val presentation = answerSourcePresentation(
                    status = message.answerStatus,
                    answer = message.text,
                    sources = message.sources,
                )
                Column(
                    modifier = modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
                ) {
                    ChatAssistantCard(
                        text = message.text,
                        scopeLabel = stringResource(landScopeCaption(message.landScope)),
                        annotatedText = answerAnnotations(presentation.segments),
                        // A newly appended answer is announced politely, exactly like the abstention.
                        liveRegionMode = LiveRegionMode.Polite,
                    )
                    if (presentation.cards.isNotEmpty()) {
                        SourceCardsSection(cards = presentation.cards)
                    }
                }
            }

            // An abstention is a decoded answer, not a failure: it stays in the transcript with the
            // caution tokens, an explicit text state label, and the server message verbatim. The
            // limitation and next step are the sentences already inside that message.
            AnswerStatus.abstained -> ChatAbstentionCard(
                modifier = modifier,
                scopeLabel = stringResource(landScopeCaption(message.landScope)),
                stateLabel = stringResource(Res.string.chat_answer_state_abstained),
                text = message.text,
            )

            // A clarification appends no entry today (its answer is empty), so this stays a neutral
            // rendering and makes the mapping exhaustive, so a new status cannot fall through.
            AnswerStatus.needs_land_clarification ->
                ChatAssistantCard(text = message.text, modifier = modifier.fillMaxWidth())
        }
    }
}

/** The neutral assistant card shared by a supported answer and a defensive clarification. */
@Composable
private fun ChatAssistantCard(
    text: String,
    modifier: Modifier = Modifier,
    scopeLabel: String? = null,
    annotatedText: AnnotatedString? = null,
    liveRegionMode: LiveRegionMode? = null,
) {
    ChatBubble(
        modifier = modifier.fillMaxWidth(),
        label = stringResource(Res.string.chat_speaker_assistant),
        labelColor = MaterialTheme.colorScheme.primary,
        scopeLabel = scopeLabel,
        text = text,
        annotatedText = annotatedText,
        containerColor = MaterialTheme.colorScheme.surfaceContainerLowest,
        liveRegionMode = liveRegionMode,
    )
}

/**
 * The scope caption for one answer, mapped exhaustively from the decoded [LandContextMode]. There
 * is no `else`: a fourth mode would break compilation instead of silently rendering nothing. The
 * caption only states which stored lands were taken into account — it never names a land or id,
 * never implies the land details prove eligibility, and adds no confident or success affordance.
 */
private fun landScopeCaption(scope: LandContextMode): StringResource = when (scope) {
    LandContextMode.general -> Res.string.chat_land_scope_general
    LandContextMode.all_active -> Res.string.chat_land_scope_all_active
    LandContextMode.selected -> Res.string.chat_land_scope_selected
}

/**
 * Builds the annotated reply body when the reply has reference markers, or returns null when there
 * is nothing to annotate so the plain `String` body renders unchanged. A reference numeral is drawn
 * as a superscript numeral: a position/size cue first and colour second, never a tappable link (the
 * source card holds the one large, labelled control).
 */
@Composable
private fun answerAnnotations(segments: List<AnswerSegment>): AnnotatedString? {
    if (segments.none { it is AnswerSegment.Reference }) return null
    val referenceStyle = SpanStyle(
        baselineShift = BaselineShift.Superscript,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    return buildAnnotatedString {
        segments.forEach { segment ->
            when (segment) {
                is AnswerSegment.Text -> append(segment.text)
                is AnswerSegment.Reference -> withStyle(referenceStyle) {
                    append(segment.number.toString())
                }
            }
        }
    }
}

/** The neutral working notice: one tonal card, text first, announced politely once. */
@Composable
internal fun ChatNoticeBubble(
    text: String,
    modifier: Modifier = Modifier,
    liveRegionMode: LiveRegionMode? = null,
) {
    ChatBubble(
        modifier = modifier.fillMaxWidth(),
        label = stringResource(Res.string.chat_speaker_assistant),
        labelColor = MaterialTheme.colorScheme.onSurfaceVariant,
        text = text,
        containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        borderColor = null,
        liveRegionMode = liveRegionMode,
    )
}

/**
 * One abstention: a decoded answer that says the assistant could not confirm it. The caution
 * boundary, the `Asistente` label, the scope caption and the explicit `Sin respuesta segura` state
 * label all stay inside one merged, politely announced node, so the caution is never carried by
 * colour alone and the entry never looks like a supported answer. The warning glyph is decorative.
 */
@Composable
private fun ChatAbstentionCard(
    text: String,
    scopeLabel: String,
    stateLabel: String,
    modifier: Modifier = Modifier,
) {
    val semanticColors = LocalManijeroSemanticColors.current
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = ManijeroShapes.Large,
        color = semanticColors.cautionSurface,
        contentColor = MaterialTheme.colorScheme.onSurface,
        border = BorderStroke(ManijeroLayout.BorderWidth, semanticColors.caution),
    ) {
        Row(
            modifier = Modifier.padding(ManijeroSpacing.Comfortable),
            horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
            verticalAlignment = Alignment.Top,
        ) {
            ManijeroIcon(
                resource = Res.drawable.ic_warning,
                contentDescription = null,
                size = ManijeroIconSize.Inline,
                tint = semanticColors.caution,
            )
            Column(
                modifier = Modifier
                    .weight(1f)
                    .semantics(mergeDescendants = true) {
                        liveRegion = LiveRegionMode.Polite
                    },
                verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
            ) {
                Text(
                    text = stringResource(Res.string.chat_speaker_assistant),
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = scopeLabel,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = stateLabel,
                    style = MaterialTheme.typography.labelLarge,
                    color = semanticColors.caution,
                )
                Text(
                    text = text,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }
    }
}

/**
 * One transcript entry surface. The speaker is always written out as a label so entries stay
 * distinguishable without relying on colour, and the label, optional scope caption, optional state
 * label and body are merged into a single node for assistive technologies. [borderColor] is
 * nullable so the person's own entry and the working notice can be borderless; [textColor] follows
 * the container so the primary user entry stays readable. The scope caption is neutral plain text
 * (never a badge, checkmark, or success colour) and renders directly below the speaker label and
 * above any [stateLabel]/body. When [annotatedText] is present it renders instead of the plain
 * [text] (the same body with citation reference numerals), so every other call site keeps a plain
 * `String` body.
 */
@Composable
private fun ChatBubble(
    label: String,
    labelColor: Color,
    text: String,
    containerColor: Color,
    modifier: Modifier = Modifier,
    borderColor: Color? = MaterialTheme.colorScheme.outlineVariant,
    textColor: Color = MaterialTheme.colorScheme.onSurface,
    scopeLabel: String? = null,
    stateLabel: String? = null,
    stateLabelColor: Color = labelColor,
    liveRegionMode: LiveRegionMode? = null,
    annotatedText: AnnotatedString? = null,
) {
    Surface(
        modifier = modifier.semantics(mergeDescendants = true) {
            if (liveRegionMode != null) {
                liveRegion = liveRegionMode
            }
        },
        shape = ManijeroShapes.Large,
        color = containerColor,
        contentColor = textColor,
        border = borderColor?.let { BorderStroke(ManijeroLayout.BorderWidth, it) },
    ) {
        Column(
            modifier = Modifier.padding(ManijeroSpacing.Comfortable),
            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelLarge,
                color = labelColor,
            )
            if (scopeLabel != null) {
                Text(
                    text = scopeLabel,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (stateLabel != null) {
                Text(
                    text = stateLabel,
                    style = MaterialTheme.typography.labelLarge,
                    color = stateLabelColor,
                )
            }
            if (annotatedText != null) {
                Text(
                    text = annotatedText,
                    style = MaterialTheme.typography.bodyLarge,
                    color = textColor,
                )
            } else {
                Text(
                    text = text,
                    style = MaterialTheme.typography.bodyLarge,
                    color = textColor,
                )
            }
        }
    }
}
