package com.jamarglex.manijero

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.backhandler.BackHandler
import com.jamarglex.manijero.chat.AnswerService
import com.jamarglex.manijero.chat.ChatHomeScreen
import com.jamarglex.manijero.chat.UnavailableAnswerService
import com.jamarglex.manijero.coverage.CoverageScreen
import com.jamarglex.manijero.lands.AddLandAction
import com.jamarglex.manijero.lands.AddLandScreen
import com.jamarglex.manijero.lands.AddLandState
import com.jamarglex.manijero.lands.EditLandAction
import com.jamarglex.manijero.lands.EditLandFailure
import com.jamarglex.manijero.lands.EditLandScreen
import com.jamarglex.manijero.lands.EditLandState
import com.jamarglex.manijero.lands.Land
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
import com.jamarglex.manijero.privacy.PrivacyScreen
import com.jamarglex.manijero.theme.ManijeroTheme

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
                    onQueryChange = { query ->
                        landListState = landListState.reduce(LandListAction.QueryChanged(query))
                    },
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
