package com.jamarglex.manijero.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Checkbox
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.testTag
import com.jamarglex.manijero.ChatHomeAction
import com.jamarglex.manijero.ChatHomeState
import com.jamarglex.manijero.ChatMessage
import com.jamarglex.manijero.SubmissionPhase
import com.jamarglex.manijero.design.ManijeroBrandMark
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.design.ManijeroIcon
import com.jamarglex.manijero.design.ManijeroScreen
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroShapes
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
import manijero.shared.generated.resources.chat_home_retention_checkbox
import manijero.shared.generated.resources.chat_home_retention_label
import manijero.shared.generated.resources.chat_home_retention_link
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
import manijero.shared.generated.resources.welcome_can
import manijero.shared.generated.resources.welcome_dismiss
import manijero.shared.generated.resources.welcome_lands
import manijero.shared.generated.resources.welcome_limits
import manijero.shared.generated.resources.welcome_privacy
import manijero.shared.generated.resources.welcome_title
import org.jetbrains.compose.resources.stringResource

/**
 * The assistant surface inside the one app shell: one tonal hero, the transcript in order, the
 * accepted suggested questions, the always-visible privacy summary, and the composer (question
 * field, round send button and retention choice) pinned to the bottom of the screen.
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
    showWelcome: Boolean = false,
    onDismissWelcome: () -> Unit = {},
    onInspect: ((ChatMessage) -> Unit)? = null,
    onRetentionInfoClick: (() -> Unit)? = null,
) {
    val transcriptEndRequester = remember { BringIntoViewRequester() }
    val scrollKey = transcriptScrollKey(state)
    val initialScrollKey = remember { scrollKey }
    LaunchedEffect(scrollKey) {
        if (scrollKey != initialScrollKey) transcriptEndRequester.bringIntoView()
    }

    ManijeroScreen(
        modifier = modifier,
        // The composer stays attached to the bottom of the screen; the transcript scrolls above it.
        bottomBar = {
            ChatComposer(
                state = state,
                onAction = onAction,
                onRetentionInfoClick = onRetentionInfoClick,
            )
        },
    ) {
        if (showWelcome) WelcomeCard(onDismiss = onDismissWelcome)
        ChatHero()

        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
        ) {
            state.messages.forEachIndexed { index, message ->
                ChatMessageBubble(
                    message = message,
                    index = index,
                    onFeedback = { messageIndex, rating ->
                        onAction(ChatHomeAction.FeedbackClicked(messageIndex, rating))
                    },
                    onInspect = onInspect,
                )
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
        ChatFooter(
            onPrivacyClick = onPrivacyClick,
            onCoverageClick = onCoverageClick,
        )
    }
}

/**
 * The first-use welcome card: what the assistant answers, what it does not, and how land data is
 * handled, in the accepted facts only. It is dismissible, blocks nothing, and adds no heading
 * semantics (the chat keeps exactly one heading).
 */
@Composable
private fun WelcomeCard(onDismiss: () -> Unit) {
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        Text(
            text = stringResource(Res.string.welcome_title),
            style = MaterialTheme.typography.titleMedium,
        )
        listOf(
            Res.string.welcome_can,
            Res.string.welcome_limits,
            Res.string.welcome_privacy,
            Res.string.welcome_lands,
        ).forEach { line ->
            Text(text = stringResource(line), style = MaterialTheme.typography.bodyLarge)
        }
        OutlinedButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(Res.string.welcome_dismiss))
        }
    }
}

/**
 * The hero: the 32 dp identity mark beside the one heading of the surface and the accepted
 * description. The mark is identity only (decorative), never a verification cue, and the block adds
 * no date, badge, status or greeting.
 */
@Composable
private fun ChatHero() {
    ManijeroCard(tone = ManijeroCardTone.Tonal, shape = ManijeroShapes.ExtraLarge) {
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
                    shape = ManijeroShapes.Pill,
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

/**
 * The pinned composer: the question field with a round send button beside it (messaging-app
 * style), and the short `Ayúdanos a mejorar` choice below them. The button is icon-only on purpose; its
 * accessible name is the visible-action word `Preguntar`, so screen readers and keyboard users still
 * hear the action. The choice is its own control: ticking it never sends, and sending keeps it.
 */
@Composable
private fun ChatComposer(
    state: ChatHomeState,
    onAction: (ChatHomeAction) -> Unit,
    onRetentionInfoClick: (() -> Unit)?,
) {
    val askLabel = stringResource(Res.string.chat_home_ask)
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact),
        verticalAlignment = Alignment.Bottom,
    ) {
        OutlinedTextField(
            value = state.question,
            onValueChange = { onAction(ChatHomeAction.QuestionChanged(it)) },
            modifier = Modifier.weight(1f).testTag(ChatTestTags.QUESTION_FIELD),
            label = { Text(stringResource(Res.string.chat_home_question_label)) },
            placeholder = { Text(stringResource(Res.string.chat_home_question_hint)) },
            isError = state.isOverCharacterLimit,
            supportingText = if (state.isOverCharacterLimit) {
                { Text(stringResource(Res.string.chat_home_question_too_long)) }
            } else {
                null
            },
            shape = ManijeroShapes.Large,
            minLines = 1,
            maxLines = 5,
        )
        FilledIconButton(
            onClick = { onAction(ChatHomeAction.AskClicked) },
            enabled = state.canAsk,
            shape = CircleShape,
            modifier = Modifier
                // Lines up with the bottom edge of a one-line outlined field (its label sits above).
                .padding(bottom = if (state.isOverCharacterLimit) ComposerErrorLineHeight else 0.dp)
                .size(ComposerSendButtonSize)
                .testTag(ChatTestTags.ASK_BUTTON),
        ) {
            ManijeroIcon(
                resource = Res.drawable.ic_send,
                contentDescription = askLabel,
                size = ManijeroIconSize.Default,
            )
        }
    }
    RetentionChoice(
        checked = state.retainQuestions,
        onCheckedChange = { onAction(ChatHomeAction.RetentionChoiceChanged(it)) },
        onInfoClick = onRetentionInfoClick,
    )
}

/** The round send button: as tall as a one-line outlined field, well above the 48 dp target. */
private val ComposerSendButtonSize = 56.dp

/** Height of the over-limit supporting line, so the button stays level with the field box. */
private val ComposerErrorLineHeight = 20.dp

/**
 * The short `Ayúdanos a mejorar` choice: the same standing permission as the switch in `Ajustes`.
 * The checkbox is its own 48 dp control, announced as a checkbox with its state and a name that
 * says what it saves. The visible label is a separate link to the `Ajustes` section that explains
 * the full purpose (what is kept, what is never kept, and the 30-day deletion); without
 * [onInfoClick] (previews, the iOS scaffold) the label is plain text. Ticking it never sends.
 */
@Composable
private fun RetentionChoice(
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    onInfoClick: (() -> Unit)?,
) {
    val checkboxName = stringResource(Res.string.chat_home_retention_checkbox)
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(
            checked = checked,
            onCheckedChange = onCheckedChange,
            modifier = Modifier.semantics { contentDescription = checkboxName },
        )
        val label = stringResource(Res.string.chat_home_retention_label)
        if (onInfoClick != null) {
            val linkName = stringResource(Res.string.chat_home_retention_link)
            TextButton(
                onClick = onInfoClick,
                modifier = Modifier.semantics { contentDescription = linkName },
            ) {
                Text(
                    text = label,
                    style = MaterialTheme.typography.bodyMedium,
                    textDecoration = TextDecoration.Underline,
                )
            }
        } else {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(start = ManijeroSpacing.Compact),
            )
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
