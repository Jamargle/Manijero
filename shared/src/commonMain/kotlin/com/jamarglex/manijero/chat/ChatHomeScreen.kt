package com.jamarglex.manijero.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.ChatHomeAction
import com.jamarglex.manijero.ChatHomeState
import com.jamarglex.manijero.SubmissionPhase
import com.jamarglex.manijero.design.ManijeroBrandMark
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.design.ManijeroIcon
import com.jamarglex.manijero.design.ManijeroScreen
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.transcriptScrollKey
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.chat_home_ask
import manijero.shared.generated.resources.chat_home_description
import manijero.shared.generated.resources.chat_home_privacy
import manijero.shared.generated.resources.chat_home_privacy_summary
import manijero.shared.generated.resources.chat_home_question_hint
import manijero.shared.generated.resources.chat_home_question_label
import manijero.shared.generated.resources.chat_home_question_too_long
import manijero.shared.generated.resources.chat_home_suggestion_condicionalidad
import manijero.shared.generated.resources.chat_home_suggestion_sigpac
import manijero.shared.generated.resources.chat_home_suggestion_solicitud_unica
import manijero.shared.generated.resources.chat_home_suggestions_title
import manijero.shared.generated.resources.chat_home_title
import manijero.shared.generated.resources.chat_home_working
import manijero.shared.generated.resources.coverage_open
import manijero.shared.generated.resources.ic_chat
import manijero.shared.generated.resources.ic_help
import manijero.shared.generated.resources.ic_info
import manijero.shared.generated.resources.ic_send
import org.jetbrains.compose.resources.stringResource

/**
 * The assistant surface inside the one app shell: one tonal hero, the transcript in order, the
 * accepted suggested questions, the composer, and the always-visible privacy summary.
 *
 * The screen owns no request, land read or validation rule; it renders the pure state it is given.
 * Newest transcript content is brought into view once per appended element — a new entry, the
 * working indication, a failure notice, or the chooser. `transcriptScrollKey` (pure, tested) decides
 * when; the end marker below is the only thing that moves. The key at first composition is
 * remembered, so opening or returning to the chat never scrolls, and nothing else on the page
 * (composer text, focus, page bottom) is touched.
 */
@Composable
internal fun ChatHomeScreen(
    state: ChatHomeState,
    onAction: (ChatHomeAction) -> Unit,
    onPrivacyClick: (() -> Unit)? = null,
    onCoverageClick: (() -> Unit)? = null,
    clarificationLands: List<Land>? = null,
    modifier: Modifier = Modifier,
) {
    val transcriptEndRequester = remember { BringIntoViewRequester() }
    val scrollKey = transcriptScrollKey(state)
    val initialScrollKey = remember { scrollKey }
    LaunchedEffect(scrollKey) {
        if (scrollKey != initialScrollKey) transcriptEndRequester.bringIntoView()
    }

    ManijeroScreen(modifier = modifier) {
        ChatHero()

        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
        ) {
            state.messages.forEach { message ->
                ChatMessageBubble(message = message)
            }

            // A failure is state, never a transcript entry, so it can never be read as an
            // assistant answer. It is mutually exclusive with the working indication
            // (failure != null only when idle, the working notice only while submitting).
            state.failure?.let { failure ->
                ChatFailureNotice(
                    failure = failure,
                    onRetry = { onAction(ChatHomeAction.RetryClicked) },
                )
            }

            if (state.phase == SubmissionPhase.SUBMITTING) {
                ChatNoticeBubble(
                    text = stringResource(Res.string.chat_home_working),
                    liveRegionMode = LiveRegionMode.Polite,
                )
            }

            if (state.awaitingLandClarification) {
                LandClarificationChooser(
                    lands = clarificationLands?.filter { land -> land.id in state.landIdsToChoose },
                    landIdsToChoose = state.landIdsToChoose,
                    onAction = onAction,
                )
            }

            // The end-of-transcript marker: a 1dp, decorative node after every transcript element.
            // `bringIntoView` on it scrolls just enough to show the newest content, not to the bottom
            // of the page (the composer and the privacy summary stay below it). The height must not
            // be zero: `NodeCoordinator.localBoundingBoxOf` collapses an empty (zero-height) rect to
            // `Rect.Zero`, which the scroll responder then reads as "already visible at the container
            // origin" and silently drops the request (verified on the Android emulator).
            Spacer(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(1.dp)
                    .bringIntoViewRequester(transcriptEndRequester),
            )
        }

        SuggestedQuestions(onAction = onAction)
        ChatComposer(state = state, onAction = onAction)
        ChatFooter(
            onPrivacyClick = onPrivacyClick,
            onCoverageClick = onCoverageClick,
        )
    }
}

/**
 * The hero: the 32 dp identity mark beside the one heading of the surface and the accepted
 * description. The mark is identity only (decorative), never a verification cue, and the block adds
 * no date, badge, status or greeting.
 */
@Composable
private fun ChatHero() {
    ManijeroCard(tone = ManijeroCardTone.Tonal) {
        // The mark sits above the heading, not beside it: at 2× text a side-by-side mark narrows the
        // title column enough to break a single word and the final question mark onto its own line.
        ManijeroBrandMark()
        Column(verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro)) {
            Text(
                text = stringResource(Res.string.chat_home_title),
                style = MaterialTheme.typography.headlineMedium,
                // The screen title is the one heading semantic on this surface.
                modifier = Modifier.semantics { heading() },
            )
            Text(
                text = stringResource(Res.string.chat_home_description),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * The three accepted example questions as wrapping, named controls. Selecting one only fills the
 * composer through [ChatHomeAction.SuggestedQuestionSelected]; it never submits. The wrapping is the
 * requirement: a question is never truncated to fit a chip.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SuggestedQuestions(onAction: (ChatHomeAction) -> Unit) {
    val suggestedQuestionResources = listOf(
        Res.string.chat_home_suggestion_solicitud_unica,
        Res.string.chat_home_suggestion_sigpac,
        Res.string.chat_home_suggestion_condicionalidad,
    )
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
    ) {
        Text(
            text = stringResource(Res.string.chat_home_suggestions_title),
            style = MaterialTheme.typography.titleMedium,
        )
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
        ) {
            suggestedQuestionResources.forEach { resource ->
                val question = stringResource(resource)
                AssistChip(
                    onClick = { onAction(ChatHomeAction.SuggestedQuestionSelected(question)) },
                    label = { Text(text = question) },
                    leadingIcon = {
                        ManijeroIcon(
                            resource = Res.drawable.ic_chat,
                            contentDescription = null,
                            size = ManijeroIconSize.Inline,
                        )
                    },
                )
            }
        }
    }
}

/** The question field plus the one visible primary action of the surface. */
@Composable
private fun ChatComposer(state: ChatHomeState, onAction: (ChatHomeAction) -> Unit) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
    ) {
        OutlinedTextField(
            value = state.question,
            onValueChange = { onAction(ChatHomeAction.QuestionChanged(it)) },
            modifier = Modifier.fillMaxWidth(),
            label = { Text(stringResource(Res.string.chat_home_question_label)) },
            placeholder = { Text(stringResource(Res.string.chat_home_question_hint)) },
            isError = state.isOverCharacterLimit,
            supportingText = if (state.isOverCharacterLimit) {
                { Text(stringResource(Res.string.chat_home_question_too_long)) }
            } else {
                null
            },
            minLines = 3,
            maxLines = 6,
        )

        // The label is visible on purpose: a person with little computer experience must never have
        // to infer the action from a lone arrow, and the send glyph stays decorative.
        Button(
            onClick = { onAction(ChatHomeAction.AskClicked) },
            enabled = state.canAsk,
            modifier = Modifier.fillMaxWidth(),
        ) {
            ManijeroIcon(
                resource = Res.drawable.ic_send,
                contentDescription = null,
                size = ManijeroIconSize.Inline,
            )
            Spacer(modifier = Modifier.width(ManijeroSpacing.Compact))
            Text(stringResource(Res.string.chat_home_ask))
        }
    }
}

/**
 * The essential facts are always visible on the chat home — before a question is asked — as plain
 * text, never colour-only. The labelled controls open the fuller notice; with no wiring (the iOS
 * scaffold and previews) only the summary line shows. The copy is the accepted copy, unchanged.
 */
@Composable
private fun ChatFooter(
    onPrivacyClick: (() -> Unit)?,
    onCoverageClick: (() -> Unit)?,
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact),
    ) {
        Text(
            text = stringResource(Res.string.chat_home_privacy_summary),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (onPrivacyClick != null) {
            TextButton(onClick = onPrivacyClick, modifier = Modifier.fillMaxWidth()) {
                ManijeroIcon(
                    resource = Res.drawable.ic_info,
                    contentDescription = null,
                    size = ManijeroIconSize.Inline,
                )
                Spacer(modifier = Modifier.width(ManijeroSpacing.Compact))
                Text(stringResource(Res.string.chat_home_privacy))
            }
        }
        if (onCoverageClick != null) {
            TextButton(onClick = onCoverageClick, modifier = Modifier.fillMaxWidth()) {
                ManijeroIcon(
                    resource = Res.drawable.ic_help,
                    contentDescription = null,
                    size = ManijeroIconSize.Inline,
                )
                Spacer(modifier = Modifier.width(ManijeroSpacing.Compact))
                Text(stringResource(Res.string.coverage_open))
            }
        }
    }
}
