package com.jamarglex.manijero

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.backhandler.BackHandler
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.BaselineShift
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.chat.AnswerSegment
import com.jamarglex.manijero.chat.AnswerService
import com.jamarglex.manijero.chat.AnswerSource
import com.jamarglex.manijero.chat.AnswerStatus
import com.jamarglex.manijero.chat.LandContextMode
import com.jamarglex.manijero.chat.RequestFailure
import com.jamarglex.manijero.chat.SourceCard
import com.jamarglex.manijero.chat.UnavailableAnswerService
import com.jamarglex.manijero.chat.answerSourcePresentation
import com.jamarglex.manijero.lands.AddLandAction
import com.jamarglex.manijero.lands.AddLandScreen
import com.jamarglex.manijero.lands.AddLandState
import com.jamarglex.manijero.lands.EditLandAction
import com.jamarglex.manijero.lands.EditLandFailure
import com.jamarglex.manijero.lands.EditLandScreen
import com.jamarglex.manijero.lands.EditLandState
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.lands.LandDetails
import com.jamarglex.manijero.lands.LandListAction
import com.jamarglex.manijero.lands.LandListConfirmation
import com.jamarglex.manijero.lands.LandListScreen
import com.jamarglex.manijero.lands.LandListState
import com.jamarglex.manijero.lands.LandRepository
import com.jamarglex.manijero.lands.LandVariety
import com.jamarglex.manijero.lands.ProductionMethod
import com.jamarglex.manijero.lands.RemoveLandAction
import com.jamarglex.manijero.lands.RemoveLandFailure
import com.jamarglex.manijero.lands.RemoveLandScreen
import com.jamarglex.manijero.lands.RemoveLandState
import com.jamarglex.manijero.lands.WaterRegime
import com.jamarglex.manijero.lands.reduce
import com.jamarglex.manijero.lands.toDraftOrNull
import com.jamarglex.manijero.lands.toEditLandState
import com.jamarglex.manijero.lands.toRemoveLandState
import com.jamarglex.manijero.privacy.PrivacyScreen
import com.jamarglex.manijero.coverage.CoverageScreen
import com.jamarglex.manijero.theme.LocalManijeroSemanticColors
import com.jamarglex.manijero.theme.ManijeroTheme
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.chat_answer_state_abstained
import manijero.shared.generated.resources.chat_home_ask
import manijero.shared.generated.resources.chat_home_clarification_continue
import manijero.shared.generated.resources.chat_home_clarification_description
import manijero.shared.generated.resources.chat_home_clarification_no_lands
import manijero.shared.generated.resources.chat_home_clarification_title
import manijero.shared.generated.resources.chat_home_description
import manijero.shared.generated.resources.chat_home_failure_service
import manijero.shared.generated.resources.chat_home_failure_unreachable
import manijero.shared.generated.resources.chat_home_privacy
import manijero.shared.generated.resources.chat_home_privacy_summary
import manijero.shared.generated.resources.coverage_open
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
import manijero.shared.generated.resources.chat_land_scope_all_active
import manijero.shared.generated.resources.chat_land_scope_general
import manijero.shared.generated.resources.chat_land_scope_selected
import manijero.shared.generated.resources.chat_source_excerpt_label
import manijero.shared.generated.resources.chat_source_issuing_body
import manijero.shared.generated.resources.chat_source_label
import manijero.shared.generated.resources.chat_source_link_unavailable
import manijero.shared.generated.resources.chat_source_location
import manijero.shared.generated.resources.chat_source_open
import manijero.shared.generated.resources.chat_source_open_description
import manijero.shared.generated.resources.chat_source_section_title
import manijero.shared.generated.resources.chat_source_verified_on
import manijero.shared.generated.resources.chat_speaker_assistant
import manijero.shared.generated.resources.chat_speaker_you

private val ContentMaxWidth = 720.dp

// Preview samples only, never shipped copy. The two abstention samples are pinned code-owned
// messages taken verbatim from the accepted abstention contract; the answered samples show the
// lead-in and orientative notice that are already part of the server `answer`.
private const val ANSWERED_SAMPLE =
    "Según los documentos oficiales revisados: presenta la solicitud dentro del plazo indicado en la convocatoria. [1] " +
        "Información orientativa basada en documentos oficiales. No sustituye el asesoramiento profesional."

// Preview-only two-source answer body: the accepted fixture's answer text with a `[1]`/`[2]` marker
// on each sentence, so the two duplicated source cards are numbered. No claim text is invented.
private const val ANSWERED_TWO_SOURCES_SAMPLE =
    "La solicitud única reúne determinadas ayudas de la PAC en una declaración anual. [1] " +
        "Revisa la convocatoria y confirma los requisitos con la oficina agraria antes de presentarla. [2]"

// Preview-only source sample, copied verbatim from contracts/examples/response-answered.json.
private val SOURCE_SAMPLE = listOf(
    AnswerSource(
        title = "Solicitud única de la PAC",
        issuing_body = "Ministerio de Agricultura, Pesca y Alimentación",
        url = "https://www.mapa.gob.es/",
        location = "Información de la solicitud única",
        published_or_updated_on = "2026-01-15",
        verified_on = "2026-10-01",
        excerpt = "La solicitud única es el procedimiento anual para solicitar determinadas ayudas de la PAC.",
    ),
)

// The accepted sample duplicated, preview-only, so the two-card layout is exercised.
private val SOURCE_SAMPLE_TWO = SOURCE_SAMPLE + SOURCE_SAMPLE

private const val ABSTAINED_SAMPLE_NO_EVIDENCE =
    "No he encontrado esta información en los documentos oficiales que tengo. " +
        "Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."

private const val ABSTAINED_SAMPLE_FALSE_PREMISE =
    "No puedo confirmar ese dato con los documentos oficiales revisados. " +
        "Comprueba el nombre o el número exacto con tu oficina comarcal agraria o con tu cooperativa."

// The one-time launch hydration of the default lands list. It runs inside `remember` so repeated
// recomposition never reads again; later reads happen on entry, retry and after a save or an edit.
internal fun initialLandListState(repository: LandRepository?): LandListState =
    repository?.let { store ->
        runCatching { store.list() }.fold(
            onSuccess = { lands -> LandListState(lands = lands) },
            onFailure = { LandListState(loadFailed = true) },
        )
    } ?: LandListState()

/**
 * Composition root. The answer service is injected so transport and endpoint decisions
 * stay outside the UI; until the backend exposes `/ask` the default reports that no
 * answer service is configured instead of inventing an answer.
 *
 * [landRepository] is the single local land store, injected by each platform entry point. When it is
 * injected the app opens on `Mis terrenos`; when it is absent (the iOS scaffold and previews) the
 * lands destination is omitted instead of creating a platform-specific store in common code, and
 * the assistant is the launch screen.
 *
 * Every destination renders inside the one [AppShell]; the route table itself is pure and lives in
 * `AppNavigation.kt`.
 */
@Suppress("DEPRECATION")
@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun App(
    landRepository: LandRepository? = null,
    answerService: AnswerService = UnavailableAnswerService,
) {
    val scope = rememberCoroutineScope()
    // The chat reads the land list at submit time and again on every retry, so a land added, edited
    // or removed after the conversation started is reflected in the next request. With no repository
    // (the iOS scaffold and previews) the accepted `general` request is used.
    val conversation = remember(answerService, scope, landRepository) {
        ChatConversation(
            answerService = answerService,
            scope = scope,
            landsProvider = { landRepository?.list().orEmpty() },
        )
    }
    val landsAvailable = landRepository != null
    // `Mis terrenos` is the launch tab when there is a local store; without one it would be a dead
    // tab, so the assistant opens instead.
    var destination by remember { mutableStateOf(initialDestination(landsAvailable)) }
    // The last top-level section that is not Help, so back from Ayuda returns to the tab it was
    // entered from instead of to itself. Detail routes (privacy, forms) keep their owning section.
    var previousSection by remember { mutableStateOf(initialSection(landsAvailable)) }
    // Where the privacy notice's own `Volver` returns to. Privacy is a detail route, not a tab.
    var privacyReturn by remember { mutableStateOf(initialDestination(landsAvailable)) }
    var addLandState by remember { mutableStateOf(AddLandState()) }
    // Hydrate the launch list once in memory so the default `Mis terrenos` frame never flashes the
    // empty state before a post-composition read can answer. The fold is the same guarded one used
    // by `readLands`; a failure keeps the list unreadable with its retry notice.
    var landListState by remember { mutableStateOf(initialLandListState(landRepository)) }
    var editLandState by remember { mutableStateOf<EditLandState?>(null) }
    var removeLandState by remember { mutableStateOf<RemoveLandState?>(null) }
    var landConfirmation by remember { mutableStateOf<LandListConfirmation?>(null) }

    // The clarification chooser reads the local lands exactly once when a clarification appears, and
    // clears them otherwise. The read is guarded and never logged: a failure shows the fallback
    // notice instead of a fabricated land. `null` means the read has not resolved yet, so the chooser
    // renders its title and explanation only and never flashes the "no lands" fallback before the
    // local read can answer. The chooser filters this list to the ids the service returned, so a land
    // that is not stored locally can never be offered.
    var clarificationLands by remember { mutableStateOf<List<Land>?>(null) }
    val awaitingLandClarification = conversation.state.awaitingLandClarification
    LaunchedEffect(awaitingLandClarification) {
        clarificationLands = if (awaitingLandClarification) {
            runCatching { landRepository?.list().orEmpty() }.getOrElse { emptyList() }
        } else {
            null
        }
    }

    // The one repeatable read of local lands: on entering the list, on retry, and after a save or
    // an edit. (The launch list is hydrated once by `initialLandListState` inside `remember`.) The
    // result is folded into a LandListAction so a failed read never looks empty and stale rows never
    // survive, and the throwable is neither logged nor shown. It is never invoked while composing,
    // so ordinary recomposition performs no read.
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

    // Which tab reads as selected. Privacy keeps the section it was opened from (its own `Volver`
    // destination), so a detail route never drops or invents a selection.
    val selectedSection = tabForDestination(
        destination = if (destination == AppDestination.Privacy) privacyReturn else destination,
        fallback = previousSection,
    )

    // Opening a section from the bars. Re-selecting the current tab is a no-op, so it never reloads
    // the land list or clears a notice the person is still reading. Entering the land section keeps
    // the accepted guarded read: a failure shows the retry notice, never a false empty list.
    val openSection: (AppSection) -> Unit = { section ->
        val target = sectionDestination(section)
        if (target != destination) {
            if (section == AppSection.Lands) {
                landConfirmation = null
                readLands()
            }
            destination = target
        }
        if (section != AppSection.Help) previousSection = section
    }

    // System back applies the same route table as the visible controls. It is installed only when
    // there is somewhere to go, so the assistant tab keeps the platform default. Leaving a form
    // with back abandons the draft exactly like its own `Cancelar`.
    val systemBackTarget = backTarget(
        destination = destination,
        previousSection = previousSection,
        privacyReturn = privacyReturn,
    )
    if (systemBackTarget != null) {
        BackHandler {
            if (systemBackTarget == AppDestination.LandList) {
                addLandState = AddLandState()
                editLandState = null
                removeLandState = null
            }
            destination = systemBackTarget
            // Back to a top-level tab also makes it the remembered section, so a later `Ayuda`
            // return, and the selected tab, agree with the screen the person is actually on.
            previousSection = rememberedSectionAfterBack(systemBackTarget, previousSection)
        }
    }

    // One shared theme and one shell for every destination; the platform entry points stay
    // theme-free. The shell owns the bars, the section callbacks and the window insets.
    ManijeroTheme {
        AppShell(
            selectedSection = selectedSection,
            landsAvailable = landRepository != null,
            navigationVisible = navigationVisible(destination),
            onSectionSelect = openSection,
        ) {
            when (destination) {
                AppDestination.Chat -> ChatHomeScreen(
                    state = conversation.state,
                    onAction = { action -> conversation.onAction(action) },
                    clarificationLands = clarificationLands,
                    onPrivacyClick = {
                        privacyReturn = AppDestination.Chat
                        destination = AppDestination.Privacy
                    },
                    onCoverageClick = {
                        previousSection = selectedSection
                        destination = AppDestination.Coverage
                    },
                )

                // The notice needs no repository, so this destination is always reachable on
                // Android and Desktop; it reads no land and writes nothing.
                AppDestination.Privacy -> PrivacyScreen(
                    onBack = { destination = privacyReturn },
                    onCoverageClick = {
                        previousSection = selectedSection
                        destination = AppDestination.Coverage
                    },
                )
                AppDestination.Coverage -> CoverageScreen(
                    onPrivacyClick = {
                        privacyReturn = AppDestination.Coverage
                        destination = AppDestination.Privacy
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
}

@Composable
internal fun ChatHomeScreen(
    state: ChatHomeState,
    onAction: (ChatHomeAction) -> Unit,
    onPrivacyClick: (() -> Unit)? = null,
    onCoverageClick: (() -> Unit)? = null,
    clarificationLands: List<Land>? = null,
    modifier: Modifier = Modifier,
) {
    val suggestedQuestionResources = listOf(
        Res.string.chat_home_suggestion_solicitud_unica,
        Res.string.chat_home_suggestion_sigpac,
        Res.string.chat_home_suggestion_condicionalidad,
    )

    // The newest transcript content is brought into view once per appended element — a new entry, the
    // working indication, a failure notice, or the chooser. `TranscriptScrollKey` (pure, tested)
    // decides when; the marker below is the only thing that moves. The key at first composition is
    // remembered so opening or returning to the chat never scrolls, and nothing else on the page
    // (composer text, focus, page bottom) is touched.
    val transcriptEndRequester = remember { BringIntoViewRequester() }
    val scrollKey = transcriptScrollKey(state)
    val initialScrollKey = remember { scrollKey }
    LaunchedEffect(scrollKey) {
        if (scrollKey != initialScrollKey) transcriptEndRequester.bringIntoView()
    }

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
            // The 720dp content cap is centred, so a wide Desktop window reads as one column instead
            // of a column hugging the left edge. No width, spacing, or child changes.
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // Every top-level block is capped at the readable width *before* filling, so the cap is
            // real: `fillMaxWidth()` first would take the window's whole width and `widthIn(max)`
            // could no longer shrink it. Combined with the centring above, a wide Desktop window
            // shows one centred 720dp column instead of a phone layout stretched edge to edge.
            Column(
                modifier = Modifier
                    .widthIn(max = ContentMaxWidth)
                    .fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    text = stringResource(Res.string.chat_home_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                    // The screen title is the one heading semantic on this surface.
                    modifier = Modifier.semantics { heading() },
                )
                Text(
                    text = stringResource(Res.string.chat_home_description),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Column(
                modifier = Modifier
                    .widthIn(max = ContentMaxWidth)
                    .fillMaxWidth(),
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
                    LandClarificationChooser(
                        lands = clarificationLands?.filter { land -> land.id in state.landIdsToChoose },
                        landIdsToChoose = state.landIdsToChoose,
                        onAction = onAction,
                    )
                }

                // The end-of-transcript marker: a 1dp, decorative node after every transcript
                // element. `bringIntoView` on it scrolls just enough to show the newest content,
                // not to the bottom of the page (the composer and the privacy summary stay below
                // it). The height must not be zero: `NodeCoordinator.localBoundingBoxOf` collapses
                // an empty (zero-height) rect to `Rect.Zero`, which the scroll responder then
                // reads as "already visible at the container origin" and silently drops the
                // request — verified on the Android emulator (implementation finding).
                Spacer(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(1.dp)
                        .bringIntoViewRequester(transcriptEndRequester),
                )
            }

            Column(
                modifier = Modifier
                    .widthIn(max = ContentMaxWidth)
                    .fillMaxWidth(),
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
                    .widthIn(max = ContentMaxWidth)
                    .fillMaxWidth(),
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
                modifier = Modifier.widthIn(max = ContentMaxWidth).fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(
                    onClick = { onAction(ChatHomeAction.AskClicked) },
                    enabled = state.canAsk,
                ) {
                    Text(stringResource(Res.string.chat_home_ask))
                }
            }

            // The essential facts are always visible on the chat home — before a question is asked —
            // as plain text, never colour-only. The labelled control opens the fuller notice; with no
            // wiring (the iOS scaffold and previews) only the summary line shows.
            Column(
                modifier = Modifier
                    .widthIn(max = ContentMaxWidth)
                    .fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = stringResource(Res.string.chat_home_privacy_summary),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (onPrivacyClick != null) {
                    TextButton(
                        onClick = onPrivacyClick,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(Res.string.chat_home_privacy))
                    }
                }
                if (onCoverageClick != null) {
                    TextButton(onClick = onCoverageClick, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(Res.string.coverage_open))
                    }
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
            // When the reply cites sources, each `[n]` marker becomes a reference numeral and every
            // cited source is shown as a card below the answer.
            AnswerStatus.answered -> {
                val presentation = answerSourcePresentation(
                    status = message.answerStatus,
                    answer = message.text,
                    sources = message.sources,
                )
                Column(
                    modifier = modifier
                        .fillMaxWidth()
                        .widthIn(max = ContentMaxWidth),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
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
            AnswerStatus.abstained -> {
                val semanticColors = LocalManijeroSemanticColors.current
                ChatBubble(
                    modifier = modifier,
                    label = stringResource(Res.string.chat_speaker_assistant),
                    labelColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    scopeLabel = stringResource(landScopeCaption(message.landScope)),
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
private fun ChatAssistantCard(
    text: String,
    modifier: Modifier = Modifier,
    scopeLabel: String? = null,
    annotatedText: AnnotatedString? = null,
    liveRegionMode: LiveRegionMode? = null,
) {
    ChatBubble(
        modifier = modifier,
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
 * The scope caption for one answer, mapped exhaustively from the decoded
 * [LandContextMode]. There is no `else`: a fourth mode would break compilation instead of silently
 * rendering nothing. The caption only states which stored lands were taken into account — it never
 * names a land or id, never implies the land details prove eligibility, and adds no confident or
 * success affordance.
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

/**
 * The cited sources of one answered reply, in payload order. The heading and one card per source are
 * rendered under the answer; nothing is reordered, merged, or deduplicated.
 */
@Composable
private fun SourceCardsSection(cards: List<SourceCard>, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .widthIn(max = ContentMaxWidth),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = stringResource(Res.string.chat_source_section_title),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onBackground,
        )
        cards.forEach { card -> SourceCardView(card = card) }
    }
}

/**
 * One cited source. The number label, title, issuing body, location, verification date, and excerpt
 * are one merged semantics node so assistive technology reads them together; the excerpt is always
 * visible in its own block and is never collapsed or truncated. The `Abrir documento oficial`
 * control is a separate focusable button whose accessible description names the source. When the URL
 * is not openable, the pinned unavailability line is shown instead and no control is offered.
 */
@Composable
private fun SourceCardView(card: SourceCard, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLowest,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics(mergeDescendants = true) {},
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                card.number?.let { number ->
                    Text(
                        text = stringResource(Res.string.chat_source_label, number),
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                Text(
                    text = card.title,
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                SourceCardDetail(stringResource(Res.string.chat_source_issuing_body, card.issuingBody))
                SourceCardDetail(stringResource(Res.string.chat_source_location, card.location))
                card.verifiedOn?.let { verifiedOn ->
                    SourceCardDetail(stringResource(Res.string.chat_source_verified_on, verifiedOn))
                }
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant,
                ) {
                    Column(
                        modifier = Modifier.padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        Text(
                            text = stringResource(Res.string.chat_source_excerpt_label),
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            text = card.excerpt,
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                    }
                }
            }

            val link = card.link
            if (link != null) {
                // One best-effort open: the platform URI handler is the only path, and a platform
                // that refuses (e.g. Desktop without AWT BROWSE support) must never crash the screen.
                val uriHandler = LocalUriHandler.current
                val openDescription =
                    stringResource(Res.string.chat_source_open_description, card.title)
                Button(
                    onClick = { runCatching { uriHandler.openUri(link) } },
                    modifier = Modifier.semantics { contentDescription = openDescription },
                ) {
                    Text(stringResource(Res.string.chat_source_open))
                }
            } else {
                SourceCardDetail(stringResource(Res.string.chat_source_link_unavailable))
            }
        }
    }
}

@Composable
private fun SourceCardDetail(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
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
        containerColor = MaterialTheme.colorScheme.surfaceContainerLowest,
        liveRegionMode = liveRegionMode,
    )
}

/**
 * The land chooser shown while a clarification is pending. It lists each offered land by its saved
 * name and known attributes (reused from the accepted land strings) with a multi-select checkbox, and
 * one primary `Continuar` enabled only once at least one land is selected. Nothing is renamed,
 * reordered, or invented: the list is already filtered to the service's opaque ids and the local
 * store's order.
 *
 * [lands] is `null` while the guarded local read has not resolved yet, so only the title and the
 * explanation show and the "cannot show your lands" fallback can never flash before the read answers.
 * A resolved list with no matching land (or a failed read) shows that fallback and no control, so a
 * land can never be fabricated.
 *
 * Each row is one merged-semantics checkbox control (label + details + checked state, never colour
 * alone) and the whole control meets the large-target guidance.
 */
@Composable
private fun LandClarificationChooser(
    lands: List<Land>?,
    landIdsToChoose: List<String>,
    onAction: (ChatHomeAction) -> Unit,
    modifier: Modifier = Modifier,
) {
    var selectedIds by remember(landIdsToChoose) { mutableStateOf(emptySet<String>()) }
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .widthIn(max = ContentMaxWidth),
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLowest,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = stringResource(Res.string.chat_home_clarification_title),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                text = stringResource(Res.string.chat_home_clarification_description),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            when {
                // The local read has not resolved yet: no fallback, no rows, and no control.
                lands == null -> Unit

                lands.isEmpty() -> Text(
                    text = stringResource(Res.string.chat_home_clarification_no_lands),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                else -> {
                    lands.forEach { land ->
                        val checked = land.id in selectedIds
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .toggleable(
                                    value = checked,
                                    role = Role.Checkbox,
                                    onValueChange = { isChecked ->
                                        selectedIds = if (isChecked) {
                                            selectedIds + land.id
                                        } else {
                                            selectedIds - land.id
                                        }
                                    },
                                )
                                .padding(vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Checkbox(checked = checked, onCheckedChange = null)
                            Column(
                                modifier = Modifier.padding(start = 12.dp),
                                verticalArrangement = Arrangement.spacedBy(4.dp),
                            ) {
                                Text(
                                    text = land.name,
                                    style = MaterialTheme.typography.bodyLarge,
                                    color = MaterialTheme.colorScheme.onSurface,
                                )
                                LandDetails(
                                    zone = land.zone,
                                    municipality = land.municipality,
                                    variety = land.variety,
                                    varietyOther = land.varietyOther,
                                    areaHectares = land.areaHectares,
                                    treeCount = land.treeCount,
                                    waterRegime = land.waterRegime,
                                    productionMethod = land.productionMethod,
                                )
                            }
                        }
                    }
                    Button(
                        onClick = {
                            onAction(ChatHomeAction.LandChoiceSubmitted(selectedIds.toList()))
                        },
                        enabled = selectedIds.isNotEmpty(),
                    ) {
                        Text(stringResource(Res.string.chat_home_clarification_continue))
                    }
                }
            }
        }
    }
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
 * distinguishable without relying on color, and the label, optional scope caption, optional state
 * label, and text are merged into a single node for assistive technologies. [borderColor],
 * [scopeLabel], [stateLabel], and [stateLabelColor] are defaulted so existing call sites stay
 * unchanged. The scope caption is neutral plain text (never a badge, checkmark, or success color) and
 * renders directly below the speaker label and above any [stateLabel]/body. When [annotatedText] is
 * present it renders instead of the plain [text] (the same body with citation reference numerals), so
 * every other call site keeps a plain `String` body.
 */
@Composable
private fun ChatBubble(
    label: String,
    labelColor: Color,
    text: String,
    containerColor: Color,
    modifier: Modifier = Modifier,
    borderColor: Color = MaterialTheme.colorScheme.outlineVariant,
    scopeLabel: String? = null,
    stateLabel: String? = null,
    stateLabelColor: Color = labelColor,
    liveRegionMode: LiveRegionMode? = null,
    annotatedText: AnnotatedString? = null,
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
                    color = MaterialTheme.colorScheme.onSurface,
                )
            } else {
                Text(
                    text = text,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }
    }
}

@Preview(name = "Chat home with examples")
@Composable
private fun ChatHomePreview() {
    ManijeroTheme { ChatHomeScreen(ChatHomeState(), {}) }
}

@Preview(name = "Chat home with privacy summary and control")
@Composable
private fun ChatHomePrivacyPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(),
            onAction = {},
            onPrivacyClick = {},
        )
    }
}

@Preview(name = "Chat home narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeSuggestionsNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(question = "¿Qué obligaciones tengo por la condicionalidad?"),
            onAction = {},
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
        )
    }
}

@Preview(name = "Chat home wide window", widthDp = 1000)
@Composable
private fun ChatHomeWideWindowPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(Speaker.ASSISTANT, ANSWERED_SAMPLE, AnswerStatus.answered, SOURCE_SAMPLE),
                ),
            ),
            onAction = {},
            onPrivacyClick = {},
        )
    }
}

@Preview(name = "Chat home long conversation, large text", fontScale = 1.3f)
@Composable
private fun ChatHomeLongConversationLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                question = "¿Puedo regar hoy?",
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Cuánto cuesta matricular un tractor viejo?"),
                    ChatMessage(Speaker.ASSISTANT, ABSTAINED_SAMPLE_NO_EVIDENCE, AnswerStatus.abstained),
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(Speaker.ASSISTANT, ANSWERED_SAMPLE, AnswerStatus.answered, SOURCE_SAMPLE),
                    ChatMessage(Speaker.USER, "¿Qué obligaciones tengo por la condicionalidad?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_TWO_SOURCES_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE_TWO,
                        LandContextMode.all_active,
                    ),
                ),
            ),
            onAction = {},
            onPrivacyClick = {},
        )
    }
}

@Preview(name = "Chat home with answered response and one source")
@Composable
private fun ChatHomeAnsweredConversationPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(Speaker.ASSISTANT, ANSWERED_SAMPLE, AnswerStatus.answered, SOURCE_SAMPLE),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home with answered response and two sources")
@Composable
private fun ChatHomeAnsweredTwoSourcesPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_TWO_SOURCES_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE_TWO,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home source card narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeSourceCardNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_TWO_SOURCES_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE_TWO,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home land scope, all lands")
@Composable
private fun ChatHomeLandScopeAllActivePreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE,
                        LandContextMode.all_active,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home land scope, selected lands")
@Composable
private fun ChatHomeLandScopeSelectedPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE,
                        LandContextMode.selected,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home land scope, abstention with all lands")
@Composable
private fun ChatHomeLandScopeAbstainedPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Cuánto cuesta matricular un tractor viejo?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ABSTAINED_SAMPLE_NO_EVIDENCE,
                        AnswerStatus.abstained,
                        emptyList(),
                        LandContextMode.all_active,
                    ),
                ),
            ),
            onAction = {},
        )
    }
}

@Preview(name = "Chat home land scope narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeLandScopeNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                messages = listOf(
                    ChatMessage(Speaker.USER, "¿Qué necesito preparar para la solicitud única?"),
                    ChatMessage(
                        Speaker.ASSISTANT,
                        ANSWERED_SAMPLE,
                        AnswerStatus.answered,
                        SOURCE_SAMPLE,
                        LandContextMode.selected,
                    ),
                ),
            ),
            onAction = {},
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
                    ChatMessage(Speaker.ASSISTANT, ANSWERED_SAMPLE, AnswerStatus.answered, SOURCE_SAMPLE),
                ),
            ),
            onAction = {},
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
        )
    }
}

// Preview-only sample lands for the chooser: the saved-name title plus known attributes, nothing a
// real store would not hold. The ids are opaque local ids and are never shown.
@Suppress("LongParameterList")
private fun clarificationLand(
    id: String,
    name: String,
    zone: String? = null,
    municipality: String? = null,
    variety: LandVariety = LandVariety.UNKNOWN,
    varietyOther: String? = null,
    areaHectares: Double? = null,
    treeCount: Int? = null,
    waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
) = Land(
    id = id,
    name = name,
    zone = zone,
    municipality = municipality,
    variety = variety,
    varietyOther = varietyOther,
    areaHectares = areaHectares,
    treeCount = treeCount,
    waterRegime = waterRegime,
    productionMethod = productionMethod,
    createdAtEpochMillis = 0,
    updatedAtEpochMillis = 0,
)

@Preview(name = "Chat home clarification chooser while the local read resolves")
@Composable
private fun ChatHomeClarificationLoadingPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                lastResponseStatus = AnswerStatus.needs_land_clarification,
                landIdsToChoose = listOf("land-1", "land-2"),
            ),
            onAction = {},
            // `null` is the unresolved guarded local read: title and explanation only, never the
            // "no puedo mostrar tus terrenos" fallback.
            clarificationLands = null,
        )
    }
}

@Preview(name = "Chat home clarification chooser, two lands")
@Composable
private fun ChatHomeClarificationTwoLandsPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                lastResponseStatus = AnswerStatus.needs_land_clarification,
                landIdsToChoose = listOf("land-1", "land-2"),
            ),
            onAction = {},
            clarificationLands = listOf(
                clarificationLand(
                    id = "land-1",
                    name = "Los Olivos",
                    zone = "Camino de la Fuente",
                    variety = LandVariety.PICUAL,
                    areaHectares = 1.5,
                    treeCount = 85,
                    waterRegime = WaterRegime.IRRIGATED,
                ),
                clarificationLand(
                    id = "land-2",
                    name = "La Loma",
                    zone = "Linde del arroyo",
                    variety = LandVariety.OTHER,
                    varietyOther = "Royal de Cazorla",
                    waterRegime = WaterRegime.DRYLAND,
                ),
            ),
        )
    }
}

@Preview(name = "Chat home clarification chooser, one land")
@Composable
private fun ChatHomeClarificationOneLandPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                lastResponseStatus = AnswerStatus.needs_land_clarification,
                landIdsToChoose = listOf("land-1"),
            ),
            onAction = {},
            clarificationLands = listOf(
                clarificationLand(
                    id = "land-1",
                    name = "Los Olivos",
                    zone = "Camino de la Fuente",
                    municipality = "Martos",
                    variety = LandVariety.ARBEQUINA,
                    areaHectares = 2.5,
                    treeCount = 85,
                    productionMethod = ProductionMethod.ORGANIC,
                ),
            ),
        )
    }
}

@Preview(name = "Chat home clarification chooser narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun ChatHomeClarificationNarrowLargeTextPreview() {
    ManijeroTheme {
        ChatHomeScreen(
            state = ChatHomeState(
                lastResponseStatus = AnswerStatus.needs_land_clarification,
                landIdsToChoose = listOf("land-1", "land-2"),
            ),
            onAction = {},
            clarificationLands = listOf(
                clarificationLand(
                    id = "land-1",
                    name = "Los Olivos",
                    zone = "Camino de la Fuente",
                    variety = LandVariety.PICUAL,
                    areaHectares = 1.5,
                    treeCount = 85,
                    waterRegime = WaterRegime.IRRIGATED,
                ),
                clarificationLand(
                    id = "land-2",
                    name = "La Loma",
                    zone = "Linde del arroyo",
                    variety = LandVariety.OTHER,
                    varietyOther = "Royal de Cazorla",
                    waterRegime = WaterRegime.DRYLAND,
                ),
            ),
        )
    }
}
