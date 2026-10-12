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
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.chat.AnswerService
import com.jamarglex.manijero.chat.UnavailableAnswerService
import com.jamarglex.manijero.lands.AddLandAction
import com.jamarglex.manijero.lands.AddLandScreen
import com.jamarglex.manijero.lands.AddLandState
import com.jamarglex.manijero.lands.LandRepository
import com.jamarglex.manijero.lands.reduce
import com.jamarglex.manijero.lands.toDraftOrNull
import org.jetbrains.compose.resources.stringResource
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.add_land_saved
import manijero.shared.generated.resources.chat_home_ask
import manijero.shared.generated.resources.chat_home_description
import manijero.shared.generated.resources.chat_home_lands
import manijero.shared.generated.resources.chat_home_needs_land_clarification
import manijero.shared.generated.resources.chat_home_question_hint
import manijero.shared.generated.resources.chat_home_question_label
import manijero.shared.generated.resources.chat_home_question_too_long
import manijero.shared.generated.resources.chat_home_suggestion_condicionalidad
import manijero.shared.generated.resources.chat_home_suggestion_sigpac
import manijero.shared.generated.resources.chat_home_suggestion_solicitud_unica
import manijero.shared.generated.resources.chat_home_suggestions_title
import manijero.shared.generated.resources.chat_home_title
import manijero.shared.generated.resources.chat_home_working
import manijero.shared.generated.resources.chat_speaker_assistant
import manijero.shared.generated.resources.chat_speaker_you

private val ContentMaxWidth = 720.dp

/** The only two shared destinations until a real navigation need appears. */
private enum class AppDestination { Chat, AddLand }

/**
 * Composition root. The answer service is injected so transport and endpoint decisions
 * stay outside the UI; until the backend exposes `/ask` the default reports that no
 * answer service is configured instead of inventing an answer.
 *
 * [landRepository] is the single local land store, injected by each platform entry point. When it is
 * absent (the iOS scaffold and previews) the lands affordance stays unavailable instead of creating
 * a platform-specific store in common code.
 */
@Composable
fun App(
    landRepository: LandRepository? = null,
    answerService: AnswerService = UnavailableAnswerService,
) {
    val scope = rememberCoroutineScope()
    val conversation = remember(answerService, scope) {
        ChatConversation(answerService = answerService, scope = scope)
    }
    var destination by remember { mutableStateOf(AppDestination.Chat) }
    var addLandState by remember { mutableStateOf(AddLandState()) }
    var landSaved by remember { mutableStateOf(false) }

    when (destination) {
        AppDestination.Chat -> ChatHomeScreen(
            state = conversation.state,
            onAction = { action ->
                conversation.onAction(action)
                landSaved = false
            },
            onLandsClick = if (landRepository == null) {
                null
            } else {
                {
                    addLandState = AddLandState()
                    landSaved = false
                    destination = AppDestination.AddLand
                }
            },
            landSavedConfirmation = landSaved,
        )

        AppDestination.AddLand -> {
            val repository = landRepository
            AddLandScreen(
                state = addLandState,
                onAction = { action ->
                    val reduced = addLandState.reduce(action)
                    addLandState = reduced
                    if (action is AddLandAction.SaveClicked && repository != null) {
                        val draft = reduced.toDraftOrNull()
                        if (draft != null) {
                            val saved = runCatching { repository.create(draft) }.isSuccess
                            if (saved) {
                                addLandState = AddLandState()
                                landSaved = true
                                destination = AppDestination.Chat
                            } else {
                                addLandState = reduced.reduce(AddLandAction.SaveFailed)
                            }
                        }
                    }
                },
                onCancel = {
                    addLandState = AddLandState()
                    destination = AppDestination.Chat
                },
            )
        }
    }
}

@Composable
internal fun ChatHomeScreen(
    state: ChatHomeState,
    onAction: (ChatHomeAction) -> Unit,
    onLandsClick: (() -> Unit)?,
    modifier: Modifier = Modifier,
    landSavedConfirmation: Boolean = false,
) {
    val suggestedQuestionResources = listOf(
        Res.string.chat_home_suggestion_solicitud_unica,
        Res.string.chat_home_suggestion_sigpac,
        Res.string.chat_home_suggestion_condicionalidad,
    )

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

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = ContentMaxWidth),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = stringResource(Res.string.chat_home_suggestions_title),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                )
                suggestedQuestionResources.forEach { questionResource ->
                    val questionText = stringResource(questionResource)
                    OutlinedButton(
                        onClick = {
                            onAction(ChatHomeAction.SuggestedQuestionSelected(questionText))
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            text = questionText,
                            modifier = Modifier.fillMaxWidth(),
                            textAlign = TextAlign.Start,
                        )
                    }
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
                TextButton(
                    onClick = { onLandsClick?.invoke() },
                    enabled = onLandsClick != null,
                ) {
                    Text(stringResource(Res.string.chat_home_lands))
                }
            }

            if (landSavedConfirmation) {
                Text(
                    text = stringResource(Res.string.add_land_saved),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier
                        .fillMaxWidth()
                        .widthIn(max = ContentMaxWidth)
                        .semantics { liveRegion = LiveRegionMode.Polite },
                )
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

@Preview(name = "Chat home with examples")
@Composable
private fun ChatHomePreview() {
    MaterialTheme { ChatHomeScreen(ChatHomeState(), {}, {}) }
}

@Preview(name = "Chat home narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeSuggestionsNarrowLargeTextPreview() {
    MaterialTheme {
        ChatHomeScreen(
            state = ChatHomeState(question = "¿Qué obligaciones tengo por la condicionalidad?"),
            onAction = {},
            onLandsClick = {},
        )
    }
}

@Preview(name = "Chat home with question")
@Composable
private fun ChatHomeWithQuestionPreview() {
    MaterialTheme {
        ChatHomeScreen(
            state = ChatHomeState(question = "¿Cuándo debo revisar mi olivar?"),
            onAction = {},
            onLandsClick = {},
        )
    }
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

@Preview(name = "Chat home after saving a land")
@Composable
private fun ChatHomeLandSavedPreview() {
    MaterialTheme {
        ChatHomeScreen(
            state = ChatHomeState(),
            onAction = {},
            onLandsClick = {},
            landSavedConfirmation = true,
        )
    }
}
