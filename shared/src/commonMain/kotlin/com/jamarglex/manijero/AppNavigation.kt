package com.jamarglex.manijero

import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.add_land_title
import manijero.shared.generated.resources.connection_title
import manijero.shared.generated.resources.coverage_title
import manijero.shared.generated.resources.edit_land_title
import manijero.shared.generated.resources.inspector_title
import manijero.shared.generated.resources.land_backup_title
import manijero.shared.generated.resources.permanently_delete_land_title
import manijero.shared.generated.resources.privacy_title
import manijero.shared.generated.resources.remove_land_title
import manijero.shared.generated.resources.removed_lands_title
import org.jetbrains.compose.resources.StringResource

/**
 * The three top-level places the shell exposes as tabs, first tab first: `Mis terrenos`,
 * `Asistente`, `Ajustes`.
 *
 * `Lands` is absent from [availableSections] when no local land repository is injected, so the
 * shell can never show a destination that cannot do anything.
 */
internal enum class AppSection { Lands, Assistant, Settings }

/**
 * Every screen the composition root can show. `Privacy`, `Terrenos eliminados`, and the land form
 * routes are detail routes, not tabs; the current [AppSection] stays selected underneath them.
 */
internal enum class AppDestination {
    Chat,
    LandList,
    AddLand,
    EditLand,
    RemoveLand,
    RemovedLands,
    PermanentlyDeleteLand,
    LandBackup,
    Privacy,

    /** The `Ajustes` tab: links to `Ayuda` and to `Copia en un archivo`. */
    Settings,

    /** The `Ayuda` detail route, opened from `Ajustes` or from the chat footer. */
    Coverage,

    /** The test-build `Conexión` route under `Ayuda`; it exists only when a host injects the tools. */
    Connection,

    /**
     * The development-only `Inspección de la respuesta` detail route under `Asistente`. It is
     * reachable only from an `Inspeccionar` link, which exists only for an entry that kept an
     * inspection in a local test build.
     */
    Inspector,
}

/** The destinations the shell may show, in tab order. */
internal fun availableSections(landsAvailable: Boolean): List<AppSection> =
    AppSection.entries.filter { landsAvailable || it != AppSection.Lands }

/**
 * The screen shown after launch: `Mis terrenos` when a local land repository is injected, so the
 * saved lands are the first thing the person sees; otherwise the assistant, because a lands tab
 * without a store would be dead.
 */
internal fun initialDestination(landsAvailable: Boolean): AppDestination =
    if (landsAvailable) AppDestination.LandList else AppDestination.Chat

/** The tab that must read as selected on the first frame. */
internal fun initialSection(landsAvailable: Boolean): AppSection =
    tabForDestination(initialDestination(landsAvailable), AppSection.Assistant)

/** The top-level screen a tab opens. */
internal fun sectionDestination(section: AppSection): AppDestination = when (section) {
    AppSection.Assistant -> AppDestination.Chat
    AppSection.Lands -> AppDestination.LandList
    AppSection.Settings -> AppDestination.Settings
}

/**
 * The tab that must read as selected for [destination]. Detail routes keep the section they were
 * opened from; [fallback] is that remembered section.
 */
internal fun tabForDestination(destination: AppDestination, fallback: AppSection): AppSection =
    when (destination) {
        AppDestination.Chat,
        AppDestination.Inspector,
        -> AppSection.Assistant
        AppDestination.LandList,
        AppDestination.AddLand,
        AppDestination.EditLand,
        AppDestination.RemoveLand,
        AppDestination.RemovedLands,
        AppDestination.PermanentlyDeleteLand,
        -> AppSection.Lands

        AppDestination.Settings,
        AppDestination.LandBackup,
        AppDestination.Coverage,
        AppDestination.Connection,
        -> AppSection.Settings
        AppDestination.Privacy -> fallback
    }

/**
 * The remembered section after a back press. Landing on a top-level tab makes it the tab a later
 * `Ajustes` returns to; every other route keeps the section it was already under.
 */
internal fun rememberedSectionAfterBack(
    destination: AppDestination,
    previousSection: AppSection,
): AppSection = when (destination) {
    AppDestination.Chat -> AppSection.Assistant
    AppDestination.LandList -> AppSection.Lands
    else -> previousSection
}

/**
 * The tab bar (or rail) belongs to the three top-level screens only (owner decision 2026-11-08).
 * Every detail route, including the land forms and the deletion confirmation, hides it, so a stray
 * tab tap cannot abandon a draft or a pending decision and the way out is the top bar's up arrow.
 */
internal fun navigationVisible(destination: AppDestination): Boolean = !showsUpNavigation(destination)

/**
 * The title the top bar shows for a detail route, or `null` on the three top-level screens (which
 * keep the brand mark and `Manijero`). Every route with an up arrow has a title, so a detail screen
 * never repeats it as a large heading in its content.
 */
internal fun screenTitleResource(destination: AppDestination): StringResource? = when (destination) {
    AppDestination.Chat,
    AppDestination.LandList,
    AppDestination.Settings,
    -> null

    AppDestination.AddLand -> Res.string.add_land_title
    AppDestination.EditLand -> Res.string.edit_land_title
    AppDestination.RemoveLand -> Res.string.remove_land_title
    AppDestination.RemovedLands -> Res.string.removed_lands_title
    AppDestination.PermanentlyDeleteLand -> Res.string.permanently_delete_land_title
    AppDestination.LandBackup -> Res.string.land_backup_title
    AppDestination.Privacy -> Res.string.privacy_title
    AppDestination.Coverage -> Res.string.coverage_title
    AppDestination.Connection -> Res.string.connection_title
    AppDestination.Inspector -> Res.string.inspector_title
}

/**
 * Whether the top bar shows the up arrow. The three top-level tab screens do not (the tabs are
 * their navigation); every other route does, and the arrow goes where system back goes.
 */
internal fun showsUpNavigation(destination: AppDestination): Boolean = when (destination) {
    AppDestination.Chat,
    AppDestination.LandList,
    AppDestination.Settings,
    -> false

    else -> true
}

/**
 * The route Android system back goes to, or `null` to let the host close the app.
 *
 * [previousSection] is the last section other than `Ajustes`; [privacyReturn] and [coverageReturn]
 * are the destinations privacy and `Ayuda` were opened from. `Ajustes` always returns to the tab it
 * was entered from, never to itself.
 */
internal fun backTarget(
    destination: AppDestination,
    previousSection: AppSection,
    privacyReturn: AppDestination,
    coverageReturn: AppDestination = AppDestination.Settings,
): AppDestination? = when (destination) {
    AppDestination.Chat -> null
    AppDestination.LandList -> AppDestination.Chat
    AppDestination.AddLand,
    AppDestination.EditLand,
    AppDestination.RemoveLand,
    -> AppDestination.LandList

    AppDestination.RemovedLands -> AppDestination.LandList
    AppDestination.LandBackup -> AppDestination.Settings
    AppDestination.PermanentlyDeleteLand -> AppDestination.RemovedLands

    AppDestination.Settings -> {
        val previous = sectionDestination(previousSection)
        if (previous == AppDestination.Settings) AppDestination.Chat else previous
    }

    AppDestination.Coverage -> coverageReturn

    AppDestination.Privacy -> privacyReturn
    AppDestination.Connection -> AppDestination.Coverage
    AppDestination.Inspector -> AppDestination.Chat
}
