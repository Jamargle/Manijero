package com.jamarglex.manijero

/**
 * The three top-level places the shell exposes as tabs, first tab first: `Mis terrenos`,
 * `Asistente`, `Ayuda`.
 *
 * `Lands` is absent from [availableSections] when no local land repository is injected, so the
 * shell can never show a destination that cannot do anything.
 */
internal enum class AppSection { Lands, Assistant, Help }

/**
 * Every screen the composition root can show. `Privacy` and the three form routes are detail
 * routes, not tabs; the current [AppSection] stays selected underneath them.
 */
internal enum class AppDestination { Chat, LandList, AddLand, EditLand, RemoveLand, Privacy, Coverage }

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
    AppSection.Help -> AppDestination.Coverage
}

/**
 * The tab that must read as selected for [destination]. Detail routes keep the section they were
 * opened from; [fallback] is that remembered section.
 */
internal fun tabForDestination(destination: AppDestination, fallback: AppSection): AppSection =
    when (destination) {
        AppDestination.Chat -> AppSection.Assistant
        AppDestination.LandList,
        AppDestination.AddLand,
        AppDestination.EditLand,
        AppDestination.RemoveLand,
        -> AppSection.Lands

        AppDestination.Coverage -> AppSection.Help
        AppDestination.Privacy -> fallback
    }

/**
 * The remembered section after a back press. Landing on a top-level tab makes it the tab a later
 * `Ayuda` returns to; every other route keeps the section it was already under.
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
 * Navigation is hidden only while a land form holds unsaved input, so a stray tab tap cannot
 * abandon a draft. Privacy keeps the bars: it is a detail route with a visible `Volver`.
 */
internal fun navigationVisible(destination: AppDestination): Boolean = when (destination) {
    AppDestination.AddLand,
    AppDestination.EditLand,
    AppDestination.RemoveLand,
    -> false

    else -> true
}

/**
 * The route Android system back goes to, or `null` to let the host close the app.
 *
 * [previousSection] is the last non-help section; [privacyReturn] is the destination privacy was
 * opened from. Help always returns to the tab it was entered from, never to itself.
 */
internal fun backTarget(
    destination: AppDestination,
    previousSection: AppSection,
    privacyReturn: AppDestination,
): AppDestination? = when (destination) {
    AppDestination.Chat -> null
    AppDestination.LandList -> AppDestination.Chat
    AppDestination.AddLand,
    AppDestination.EditLand,
    AppDestination.RemoveLand,
    -> AppDestination.LandList

    AppDestination.Coverage -> {
        val previous = sectionDestination(previousSection)
        if (previous == AppDestination.Coverage) AppDestination.Chat else previous
    }

    AppDestination.Privacy -> privacyReturn
}
