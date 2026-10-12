package com.jamarglex.manijero

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
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
import manijero.shared.generated.resources.chat_home_question_hint
import manijero.shared.generated.resources.chat_home_lands
import manijero.shared.generated.resources.chat_home_question_label
import manijero.shared.generated.resources.chat_home_submitted
import manijero.shared.generated.resources.chat_home_suggestion_condicionalidad
import manijero.shared.generated.resources.chat_home_suggestion_sigpac
import manijero.shared.generated.resources.chat_home_suggestion_solicitud_unica
import manijero.shared.generated.resources.chat_home_suggestions_title
import manijero.shared.generated.resources.chat_home_title

/** The only two shared destinations until a real navigation need appears. */
private enum class AppDestination { Chat, AddLand }

/**
 * Shared app entry point.
 *
 * [landRepository] is the single local land store, injected by each platform entry point. When it is
 * absent (the iOS scaffold and previews) the lands affordance stays unavailable instead of creating
 * a platform-specific store in common code.
 */
@Composable
fun App(landRepository: LandRepository? = null) {
    var destination by remember { mutableStateOf(AppDestination.Chat) }
    var chatState by remember { mutableStateOf(ChatHomeState()) }
    var addLandState by remember { mutableStateOf(AddLandState()) }
    var landSaved by remember { mutableStateOf(false) }

    when (destination) {
        AppDestination.Chat -> ChatHomeScreen(
            state = chatState,
            onAction = { action ->
                chatState = chatState.reduce(action)
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
                    .widthIn(max = 720.dp),
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
                    .widthIn(max = 720.dp),
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
                    .widthIn(max = 720.dp),
                label = { Text(stringResource(Res.string.chat_home_question_label)) },
                placeholder = { Text(stringResource(Res.string.chat_home_question_hint)) },
                minLines = 3,
                maxLines = 6,
            )

            Row(
                modifier = Modifier.fillMaxWidth().widthIn(max = 720.dp),
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
                        .widthIn(max = 720.dp)
                        .semantics { liveRegion = LiveRegionMode.Polite },
                )
            }

            if (state.submittedQuestion != null) {
                Text(
                    text = stringResource(Res.string.chat_home_submitted),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
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
            state = ChatHomeState(question = "¿Cuándo debo revisar mi olivar?", submittedQuestion = "¿Cuándo debo revisar mi olivar?"),
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
