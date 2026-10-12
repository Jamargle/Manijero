package com.jamarglex.manijero

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import org.jetbrains.compose.resources.stringResource
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.chat_home_ask
import manijero.shared.generated.resources.chat_home_description
import manijero.shared.generated.resources.chat_home_lands
import manijero.shared.generated.resources.chat_home_needs_land_clarification
import manijero.shared.generated.resources.chat_home_question_hint
import manijero.shared.generated.resources.chat_home_question_label
import manijero.shared.generated.resources.chat_home_question_too_long
import manijero.shared.generated.resources.chat_home_title
import manijero.shared.generated.resources.chat_home_working
import manijero.shared.generated.resources.chat_speaker_assistant
import manijero.shared.generated.resources.chat_speaker_you
import com.jamarglex.manijero.chat.AnswerService
import com.jamarglex.manijero.chat.UnavailableAnswerService

private val ContentMaxWidth = 720.dp

/**
 * Composition root. The answer service is injected so transport and endpoint decisions
 * stay outside the UI; until the backend exposes `/ask` the default reports that no
 * answer service is configured instead of inventing an answer.
 */
@Composable
fun App(answerService: AnswerService = UnavailableAnswerService) {
    val scope = rememberCoroutineScope()
    val conversation = remember(answerService, scope) {
        ChatConversation(answerService = answerService, scope = scope)
    }

    ChatHomeScreen(
        state = conversation.state,
        onAction = conversation::onAction,
        onLandsClick = {},
    )
}

@Composable
internal fun ChatHomeScreen(
    state: ChatHomeState,
    onAction: (ChatHomeAction) -> Unit,
    onLandsClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 32.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = ContentMaxWidth),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    text = stringResource(Res.string.chat_home_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                )
                Text(
                    text = stringResource(Res.string.chat_home_description),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = ContentMaxWidth),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                state.messages.forEach { message ->
                    ChatMessageBubble(message = message)
                }

                if (state.phase == SubmissionPhase.SUBMITTING) {
                    ChatNoticeBubble(
                        text = stringResource(Res.string.chat_home_working),
                        liveRegionMode = LiveRegionMode.Polite,
                    )
                }

                if (state.awaitingLandClarification) {
                    ChatNoticeBubble(
                        text = stringResource(Res.string.chat_home_needs_land_clarification),
                    )
                }
            }

            OutlinedTextField(
                value = state.question,
                onValueChange = { onAction(ChatHomeAction.QuestionChanged(it)) },
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = ContentMaxWidth),
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

            Row(
                modifier = Modifier.fillMaxWidth().widthIn(max = ContentMaxWidth),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(
                    onClick = { onAction(ChatHomeAction.AskClicked) },
                    enabled = state.canAsk,
                ) {
                    Text(stringResource(Res.string.chat_home_ask))
                }
                TextButton(onClick = onLandsClick) {
                    Text(stringResource(Res.string.chat_home_lands))
                }
            }
        }
    }
}

@Composable
private fun ChatMessageBubble(message: ChatMessage, modifier: Modifier = Modifier) {
    val isUser = message.speaker == Speaker.USER
    ChatBubble(
        modifier = modifier,
        label = if (isUser) {
            stringResource(Res.string.chat_speaker_you)
        } else {
            stringResource(Res.string.chat_speaker_assistant)
        },
        labelColor = MaterialTheme.colorScheme.primary,
        text = message.text,
        containerColor = if (isUser) {
            MaterialTheme.colorScheme.surfaceVariant
        } else {
            MaterialTheme.colorScheme.surface
        },
    )
}

@Composable
private fun ChatNoticeBubble(
    text: String,
    modifier: Modifier = Modifier,
    liveRegionMode: LiveRegionMode? = null,
) {
    ChatBubble(
        modifier = modifier,
        label = stringResource(Res.string.chat_speaker_assistant),
        labelColor = MaterialTheme.colorScheme.onSurfaceVariant,
        text = text,
        containerColor = MaterialTheme.colorScheme.surface,
        liveRegionMode = liveRegionMode,
    )
}

/**
 * One transcript entry. The speaker is always written out as a label so the entries stay
 * distinguishable without relying on color, and the label and text are merged into a
 * single node for assistive technologies.
 */
@Composable
private fun ChatBubble(
    label: String,
    labelColor: Color,
    text: String,
    containerColor: Color,
    modifier: Modifier = Modifier,
    liveRegionMode: LiveRegionMode? = null,
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .widthIn(max = ContentMaxWidth)
            .semantics(mergeDescendants = true) {
                if (liveRegionMode != null) {
                    liveRegion = liveRegionMode
                }
            },
        shape = RoundedCornerShape(16.dp),
        color = containerColor,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelLarge,
                color = labelColor,
            )
            Text(
                text = text,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
    }
}

@Preview(name = "Chat home")
@Composable
private fun ChatHomePreview() {
    MaterialTheme { ChatHomeScreen(ChatHomeState(), {}, {}) }
}

@Preview(name = "Chat home with conversation")
@Composable
private fun ChatHomeConversationPreview() {
    MaterialTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Cuándo debo revisar mi olivar?"),
                    ChatMessage(Speaker.ASSISTANT, "Depende del estado del árbol y de la época del año."),
                ),
            ),
            onAction = {},
            onLandsClick = {},
        )
    }
}

@Preview(name = "Chat home while working")
@Composable
private fun ChatHomeWorkingPreview() {
    MaterialTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(ChatMessage(Speaker.USER, "¿Puedo regar hoy?")),
                phase = SubmissionPhase.SUBMITTING,
                submittedQuestion = "¿Puedo regar hoy?",
            ),
            onAction = {},
            onLandsClick = {},
        )
    }
}

@Preview(name = "Chat home over character limit")
@Composable
private fun ChatHomeOverLimitPreview() {
    MaterialTheme {
        ChatHomeScreen(
            state = ChatHomeState(question = "a".repeat(2_100)),
            onAction = {},
            onLandsClick = {},
        )
    }
}
