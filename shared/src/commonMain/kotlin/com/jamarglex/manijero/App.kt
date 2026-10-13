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
import androidx.compose.material3.ButtonDefaults
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
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.chat.UnavailableAnswerService
import com.jamarglex.manijero.lands.AddLandAction
import com.jamarglex.manijero.lands.AddLandScreen
import com.jamarglex.manijero.lands.AddLandState
import com.jamarglex.manijero.lands.EditLandAction
import com.jamarglex.manijero.lands.EditLandFailure
import com.jamarglex.manijero.lands.EditLandScreen
import com.jamarglex.manijero.lands.EditLandState
import com.jamarglex.manijero.lands.LandListAction
import com.jamarglex.manijero.lands.LandListConfirmation
import com.jamarglex.manijero.lands.LandListScreen
import com.jamarglex.manijero.lands.LandListState
import com.jamarglex.manijero.lands.LandRepository
import com.jamarglex.manijero.lands.RemoveLandAction
import com.jamarglex.manijero.lands.RemoveLandFailure
import com.jamarglex.manijero.lands.RemoveLandScreen
import com.jamarglex.manijero.lands.RemoveLandState
import com.jamarglex.manijero.lands.reduce
import com.jamarglex.manijero.lands.toDraftOrNull
import com.jamarglex.manijero.lands.toEditLandState
import com.jamarglex.manijero.lands.toRemoveLandState
import com.jamarglex.manijero.theme.LocalManijeroSemanticColors
import com.jamarglex.manijero.theme.ManijeroTheme
import org.jetbrains.compose.resources.stringResource
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.chat_answer_state_abstained
import manijero.shared.generated.resources.chat_home_ask
import manijero.shared.generated.resources.chat_home_description
import manijero.shared.generated.resources.chat_home_failure_service
import manijero.shared.generated.resources.chat_home_failure_unreachable
import manijero.shared.generated.resources.chat_home_lands
import manijero.shared.generated.resources.chat_home_needs_land_clarification
import manijero.shared.generated.resources.chat_home_question_hint
import manijero.shared.generated.resources.chat_home_question_label
import manijero.shared.generated.resources.chat_home_question_too_long
import manijero.shared.generated.resources.chat_home_retry
import manijero.shared.generated.resources.chat_home_suggestion_condicionalidad
import manijero.shared.generated.resources.chat_home_suggestion_sigpac
import manijero.shared.generated.resources.chat_home_suggestion_solicitud_unica
import manijero.shared.generated.resources.chat_home_suggestions_title
import manijero.shared.generated.resources.chat_home_title
import manijero.shared.generated.resources.chat_home_working
import manijero.shared.generated.resources.chat_speaker_assistant
import manijero.shared.generated.resources.chat_speaker_you

private val ContentMaxWidth = 720.dp

// Preview samples only, never shipped copy. The two abstention samples are pinned code-owned
// messages taken verbatim from the accepted abstention contract; the answered sample shows the
// lead-in and orientative notice that are already part of the server `answer`.
private const val ANSWERED_SAMPLE =
    "Según los documentos oficiales revisados: presenta la solicitud dentro del plazo indicado en la convocatoria. " +
        "Información orientativa basada en documentos oficiales. No sustituye el asesoramiento profesional."

private const val ABSTAINED_SAMPLE_NO_EVIDENCE =
    "No he encontrado esta información en los documentos oficiales que tengo. " +
        "Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."

private const val ABSTAINED_SAMPLE_FALSE_PREMISE =
    "No puedo confirmar ese dato con los documentos oficiales revisados. " +
        "Comprueba el nombre o el número exacto con tu oficina comarcal agraria o con tu cooperativa."

/**
 * The shared destinations: the lands list is now the parent surface of the add, edit, and remove
 * forms.
 */
private enum class AppDestination { Chat, LandList, AddLand, EditLand, RemoveLand }

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
    var landListState by remember { mutableStateOf(LandListState()) }
    var editLandState by remember { mutableStateOf<EditLandState?>(null) }
    var removeLandState by remember { mutableStateOf<RemoveLandState?>(null) }
    var landConfirmation by remember { mutableStateOf<LandListConfirmation?>(null) }

    // The single place that reads local lands: on entering the list, on retry, and after a save or
    // an edit. The result is folded into a LandListAction so a failed read never looks empty and
    // stale rows never survive, and the throwable is neither logged nor shown. It is never invoked
    // while composing, so the chat home and ordinary recomposition perform no read.
    val readLands: () -> Unit = {
        landListState = landListState.reduce(LandListAction.ReloadClicked)
        val repository = landRepository
        if (repository != null) {
            landListState = landListState.reduce(
                runCatching { repository.list() }.fold(
                    onSuccess = { LandListAction.LandsLoaded(it) },
                    onFailure = { LandListAction.LoadFailed },
                ),
            )
        }
    }

    // One shared theme for every destination; the platform entry points stay theme-free.
    ManijeroTheme {
        when (destination) {
            AppDestination.Chat -> ChatHomeScreen(
                state = conversation.state,
                onAction = { action -> conversation.onAction(action) },
                onLandsClick = if (landRepository == null) {
                    null
                } else {
                    {
                        landConfirmation = null
                        readLands()
                        destination = AppDestination.LandList
                    }
                },
            )

            AppDestination.LandList -> LandListScreen(
                state = landListState,
                confirmation = landConfirmation,
                onAddLand = {
                    addLandState = AddLandState()
                    landConfirmation = null
                    destination = AppDestination.AddLand
                },
                onEditLand = { land ->
                    editLandState = land.toEditLandState()
                    landConfirmation = null
                    destination = AppDestination.EditLand
                },
                onRemoveLand = { land ->
                    removeLandState = land.toRemoveLandState()
                    landConfirmation = null
                    destination = AppDestination.RemoveLand
                },
                onBack = { destination = AppDestination.Chat },
                onRetry = readLands,
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
                                    landConfirmation = LandListConfirmation.ADDED
                                    readLands()
                                    destination = AppDestination.LandList
                                } else {
                                    addLandState = reduced.reduce(AddLandAction.SaveFailed)
                                }
                            }
                        }
                    },
                    onCancel = {
                        addLandState = AddLandState()
                        destination = AppDestination.LandList
                    },
                )
            }

            // One record, and only that record: the update targets the edit state's own id. The
            // update is performed only on an explicit `SaveClicked`, never while composing. A null
            // result means the id is no longer stored, and a thrown failure means storage refused,
            // so neither is ever presented as saved; the values stay on screen for retry or cancel.
            AppDestination.EditLand -> editLandState?.let { renderedState ->
                val repository = landRepository
                EditLandScreen(
                    state = renderedState,
                    onAction = { action ->
                        val reduced = (editLandState ?: renderedState).reduce(action)
                        editLandState = reduced
                        if (action is EditLandAction.SaveClicked && repository != null) {
                            val draft = reduced.toDraftOrNull()
                            if (draft != null) {
                                val result = runCatching {
                                    repository.update(reduced.landId, draft)
                                }
                                when {
                                    result.getOrNull() != null -> {
                                        editLandState = null
                                        landConfirmation = LandListConfirmation.UPDATED
                                        readLands()
                                        destination = AppDestination.LandList
                                    }

                                    result.isSuccess -> editLandState = reduced.reduce(
                                        EditLandAction.SaveFailed(EditLandFailure.LAND_MISSING),
                                    )

                                    else -> editLandState = reduced.reduce(
                                        EditLandAction.SaveFailed(EditLandFailure.WRITE_FAILED),
                                    )
                                }
                            }
                        }
                    },
                    onCancel = {
                        editLandState = null
                        destination = AppDestination.LandList
                    },
                )
            }

            // One record, and only that record: the removal targets the confirmation state's own id
            // and runs `delete` only on the person's explicit `Eliminar el terreno`. Opening or
            // cancelling the confirmation writes nothing. A `false` result means the id is no longer
            // stored and a thrown failure means storage refused, so neither is ever presented as a
            // removal: both keep the confirmation on screen with a distinct plain-Spanish message.
            AppDestination.RemoveLand -> removeLandState?.let { renderedState ->
                val repository = landRepository
                RemoveLandScreen(
                    state = renderedState,
                    onRemove = {
                        val cleared = (removeLandState ?: renderedState)
                            .reduce(RemoveLandAction.RemoveClicked)
                        removeLandState = cleared
                        if (repository != null) {
                            val result = runCatching { repository.delete(cleared.landId) }
                            when {
                                result.getOrNull() == true -> {
                                    removeLandState = null
                                    landConfirmation = LandListConfirmation.REMOVED
                                    readLands()
                                    destination = AppDestination.LandList
                                }

                                result.getOrNull() == false -> removeLandState = cleared.reduce(
                                    RemoveLandAction.RemoveFailed(RemoveLandFailure.LAND_MISSING),
                                )

                                else -> removeLandState = cleared.reduce(
                                    RemoveLandAction.RemoveFailed(RemoveLandFailure.WRITE_FAILED),
                                )
                            }
                        }
                    },
                    onCancel = {
                        removeLandState = null
                        destination = AppDestination.LandList
                    },
                )
            }
        }
    }
}

@Composable
internal fun ChatHomeScreen(
    state: ChatHomeState,
    onAction: (ChatHomeAction) -> Unit,
    onLandsClick: (() -> Unit)?,
    modifier: Modifier = Modifier,
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
        }
    }
}

@Composable
private fun ChatMessageBubble(message: ChatMessage, modifier: Modifier = Modifier) {
    when (message.speaker) {
        Speaker.USER -> ChatBubble(
            modifier = modifier,
            label = stringResource(Res.string.chat_speaker_you),
            labelColor = MaterialTheme.colorScheme.primary,
            text = message.text,
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        )

        Speaker.ASSISTANT -> when (message.answerStatus) {
            // A supported answer keeps the calm neutral card. The code-owned lead-in and orientative
            // notice are already inside the server `answer`, so no client label, disclaimer, badge,
            // or "verified" affordance is added: that would be the confident treatment to avoid.
            AnswerStatus.answered -> ChatAssistantCard(text = message.text, modifier = modifier)

            // An abstention is a decoded answer, not a failure: it stays in the transcript with the
            // caution tokens, an explicit text state label, and the server message verbatim. The
            // limitation and next step are the sentences already inside that message.
            AnswerStatus.abstained -> {
                val semanticColors = LocalManijeroSemanticColors.current
                ChatBubble(
                    modifier = modifier,
                    label = stringResource(Res.string.chat_speaker_assistant),
                    labelColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    stateLabel = stringResource(Res.string.chat_answer_state_abstained),
                    stateLabelColor = semanticColors.caution,
                    text = message.text,
                    containerColor = semanticColors.cautionSurface,
                    borderColor = semanticColors.caution,
                    liveRegionMode = LiveRegionMode.Polite,
                )
            }

            // A clarification appends no entry today (its answer is empty), so this stays a neutral
            // rendering and makes the mapping exhaustive, so a new status cannot fall through.
            AnswerStatus.needs_land_clarification ->
                ChatAssistantCard(text = message.text, modifier = modifier)
        }
    }
}

/** The neutral assistant card shared by a supported answer and a defensive clarification. */
@Composable
private fun ChatAssistantCard(text: String, modifier: Modifier = Modifier) {
    ChatBubble(
        modifier = modifier,
        label = stringResource(Res.string.chat_speaker_assistant),
        labelColor = MaterialTheme.colorScheme.primary,
        text = text,
        containerColor = MaterialTheme.colorScheme.surface,
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
 * One recoverable failure. It is rendered from [ChatHomeState.failure] and never appended to the
 * transcript, so a failed request can never look like an assistant answer. The message says in
 * plain Spanish that there is no answer yet, and the always-visible `Reintentar` button resends
 * the exact original wording.
 *
 * Danger is communicated by the text plus that label, never by colour alone, and the notice is a
 * polite live region so a screen reader announces it. The retry uses the themed danger pair
 * (`error`/`onError`); no raw colour is used here.
 *
 * The reducer retains the sent wording for every failure reachable from a submission, so the
 * `Reintentar` action is always actionable here.
 */
@Composable
private fun ChatFailureNotice(
    failure: RequestFailure,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val message = when (failure) {
        RequestFailure.COULD_NOT_REACH_SERVICE ->
            stringResource(Res.string.chat_home_failure_unreachable)

        RequestFailure.SERVICE_ERROR ->
            stringResource(Res.string.chat_home_failure_service)
    }
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .widthIn(max = ContentMaxWidth)
            .semantics { liveRegion = LiveRegionMode.Polite },
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.errorContainer,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.error),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = message,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            Button(
                onClick = onRetry,
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error,
                    contentColor = MaterialTheme.colorScheme.onError,
                ),
            ) {
                Text(stringResource(Res.string.chat_home_retry))
            }
        }
    }
}

/**
 * One transcript entry. The speaker is always written out as a label so the entries stay
 * distinguishable without relying on color, and the label, optional state label, and text are merged
 * into a single node for assistive technologies. [borderColor], [stateLabel], and [stateLabelColor]
 * are defaulted so existing call sites stay unchanged.
 */
@Composable
private fun ChatBubble(
    label: String,
    labelColor: Color,
    text: String,
    containerColor: Color,
    modifier: Modifier = Modifier,
    borderColor: Color = MaterialTheme.colorScheme.outlineVariant,
    stateLabel: String? = null,
    stateLabelColor: Color = labelColor,
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
        border = BorderStroke(1.dp, borderColor),
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
            if (stateLabel != null) {
                Text(
                    text = stateLabel,
                    style = MaterialTheme.typography.labelLarge,
                    color = stateLabelColor,
                )
            }
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
    ManijeroTheme { ChatHomeScreen(ChatHomeState(), {}, {}) }
}

@Preview(name = "Chat home narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeSuggestionsNarrowLargeTextPreview() {
    ManijeroTheme {
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
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(question = "¿Cuándo debo revisar mi olivar?"),
            onAction = {},
            onLandsClick = {},
        )
    }
}

@Preview(name = "Chat home with answered response")
@Composable
private fun ChatHomeAnsweredConversationPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(Speaker.ASSISTANT, ANSWERED_SAMPLE, AnswerStatus.answered),
                ),
            ),
            onAction = {},
            onLandsClick = {},
        )
    }
}

@Preview(name = "Chat home with abstained response")
@Composable
private fun ChatHomeAbstainedConversationPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Cuánto cuesta matricular un tractor viejo?"),
                    ChatMessage(Speaker.ASSISTANT, ABSTAINED_SAMPLE_NO_EVIDENCE, AnswerStatus.abstained),
                ),
            ),
            onAction = {},
            onLandsClick = {},
        )
    }
}

@Preview(name = "Chat home with both response states")
@Composable
private fun ChatHomeBothResponseStatesPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Cuánto cuesta matricular un tractor viejo?"),
                    ChatMessage(Speaker.ASSISTANT, ABSTAINED_SAMPLE_NO_EVIDENCE, AnswerStatus.abstained),
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(Speaker.ASSISTANT, ANSWERED_SAMPLE, AnswerStatus.answered),
                ),
            ),
            onAction = {},
            onLandsClick = {},
        )
    }
}

@Preview(name = "Chat home abstention narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeAbstentionNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué dice el Real Decreto 123/2099 sobre el plazo?"),
                    ChatMessage(Speaker.ASSISTANT, ABSTAINED_SAMPLE_FALSE_PREMISE, AnswerStatus.abstained),
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
    ManijeroTheme {
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
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(question = "a".repeat(2_100)),
            onAction = {},
            onLandsClick = {},
        )
    }
}

@Preview(name = "Chat home failure, unreachable service")
@Composable
private fun ChatHomeFailureUnreachablePreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                question = "¿Puedo regar hoy?",
                messages = listOf(ChatMessage(Speaker.USER, "¿Puedo regar hoy?")),
                failure = RequestFailure.COULD_NOT_REACH_SERVICE,
                failedQuestion = "¿Puedo regar hoy?",
            ),
            onAction = {},
            onLandsClick = {},
        )
    }
}

@Preview(name = "Chat home failure narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeFailureNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                question = "¿Qué necesito preparar para la solicitud única?",
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                ),
                failure = RequestFailure.SERVICE_ERROR,
                failedQuestion = "¿Qué necesito preparar para la solicitud única?",
            ),
            onAction = {},
            onLandsClick = {},
        )
    }
}
