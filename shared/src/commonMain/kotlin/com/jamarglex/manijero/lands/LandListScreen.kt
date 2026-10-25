package com.jamarglex.manijero.lands

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
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
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.design.ManijeroEmptyState
import com.jamarglex.manijero.design.ManijeroSearchField
import com.jamarglex.manijero.design.ManijeroSectionHeader
import com.jamarglex.manijero.design.ManijeroStatCard
import com.jamarglex.manijero.design.WideWindowBreakpoint
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.add_land_production_conventional
import manijero.shared.generated.resources.add_land_production_mixed
import manijero.shared.generated.resources.add_land_production_organic
import manijero.shared.generated.resources.add_land_saved
import manijero.shared.generated.resources.add_land_unknown
import manijero.shared.generated.resources.add_land_water_dryland
import manijero.shared.generated.resources.add_land_water_irrigated
import manijero.shared.generated.resources.add_land_water_mixed
import manijero.shared.generated.resources.chat_home_lands
import manijero.shared.generated.resources.edit_land_saved
import manijero.shared.generated.resources.land_list_add
import manijero.shared.generated.resources.land_list_description
import manijero.shared.generated.resources.land_list_edit
import manijero.shared.generated.resources.land_list_edit_description
import manijero.shared.generated.resources.land_list_empty_body
import manijero.shared.generated.resources.land_list_empty_title
import manijero.shared.generated.resources.land_list_load_failed
import manijero.shared.generated.resources.add_land_variety_other
import manijero.shared.generated.resources.land_list_municipality
import manijero.shared.generated.resources.land_list_production
import manijero.shared.generated.resources.land_list_remove
import manijero.shared.generated.resources.land_list_remove_description
import manijero.shared.generated.resources.land_list_retry
import manijero.shared.generated.resources.land_list_surface
import manijero.shared.generated.resources.land_list_trees
import manijero.shared.generated.resources.land_list_variety
import manijero.shared.generated.resources.land_list_water
import manijero.shared.generated.resources.land_list_zone
import manijero.shared.generated.resources.land_search_clear
import manijero.shared.generated.resources.land_search_hint
import manijero.shared.generated.resources.land_search_label
import manijero.shared.generated.resources.land_search_no_results
import manijero.shared.generated.resources.land_summary_count_caption
import manijero.shared.generated.resources.land_summary_count_caption_filtered
import manijero.shared.generated.resources.land_summary_count_label
import manijero.shared.generated.resources.land_summary_no_data
import manijero.shared.generated.resources.land_summary_scope_all
import manijero.shared.generated.resources.land_summary_scope_filtered
import manijero.shared.generated.resources.land_summary_surface_caption
import manijero.shared.generated.resources.land_summary_surface_caption_filtered
import manijero.shared.generated.resources.land_summary_surface_label
import manijero.shared.generated.resources.land_summary_surface_value
import manijero.shared.generated.resources.land_summary_title
import manijero.shared.generated.resources.land_summary_trees_caption
import manijero.shared.generated.resources.land_summary_trees_caption_filtered
import manijero.shared.generated.resources.land_summary_trees_label
import manijero.shared.generated.resources.land_summary_trees_value_one
import manijero.shared.generated.resources.land_summary_trees_value_other
import manijero.shared.generated.resources.remove_land_removed
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

private val ContentMaxWidth = 720.dp

/** What the last successful write was, so the list confirms the right thing or nothing at all. */
enum class LandListConfirmation { ADDED, UPDATED, REMOVED }

/**
 * List of the lands saved on this device. It renders whatever [state] it receives and reports every
 * interaction through [onAddLand], [onEditLand], [onRemoveLand], [onQueryChange] or [onRetry];
 * reading, persistence and the search text itself live in the caller. Top-level navigation is the
 * app shell's job, so this screen offers no `Volver`; the tabs are the way back.
 *
 * A successful read that found no land shows the shared empty state with one `Añadir terreno`
 * action and no summary or search. Otherwise the screen summarizes the annotated surface and olive
 * count of exactly the lands it is showing, filters them as the person types, and keeps the rows
 * non-clickable with the exact saved name plus the few known details. Each row has its own visible
 * `Editar` control, and its own `Eliminar` control whose accessible description names the exact
 * saved land; selecting it opens the confirmation and writes nothing by itself. A query that
 * matches no land shows an honest panel with a named clear action, and no summary at all, so a
 * number is never stated for a land the person cannot see.
 */
@Composable
fun LandListScreen(
    state: LandListState,
    onAddLand: () -> Unit,
    onEditLand: (Land) -> Unit,
    onRemoveLand: (Land) -> Unit,
    onRetry: () -> Unit,
    onQueryChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    confirmation: LandListConfirmation? = null,
) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        // The summary grid switches on the width of the window this screen receives. It must be
        // measured here, around the padded content: the inner content column is capped at 720 dp,
        // so a breakpoint read inside it could never reach 840 dp.
        BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
            val wideWindow = maxWidth >= WideWindowBreakpoint

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 24.dp, vertical = 32.dp),
                verticalArrangement = Arrangement.spacedBy(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Column(
                    modifier = Modifier
                        .widthIn(max = ContentMaxWidth)
                        .fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    Text(
                        text = stringResource(Res.string.chat_home_lands),
                        style = MaterialTheme.typography.headlineMedium,
                        color = MaterialTheme.colorScheme.onBackground,
                    )
                    Text(
                        text = stringResource(Res.string.land_list_description),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )

                    val confirmationResource = when (confirmation) {
                        LandListConfirmation.ADDED -> Res.string.add_land_saved
                        LandListConfirmation.UPDATED -> Res.string.edit_land_saved
                        LandListConfirmation.REMOVED -> Res.string.remove_land_removed
                        null -> null
                    }
                    if (confirmationResource != null) {
                        Text(
                            text = stringResource(confirmationResource),
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier
                                .fillMaxWidth()
                                .semantics { liveRegion = LiveRegionMode.Polite },
                        )
                    }

                    when {
                        state.loadFailed -> {
                            Text(
                                text = stringResource(Res.string.land_list_load_failed),
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.error,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .semantics { liveRegion = LiveRegionMode.Polite },
                            )
                            Button(
                                onClick = onRetry,
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text(stringResource(Res.string.land_list_retry))
                            }
                        }

                        state.isEmpty -> ManijeroEmptyState(
                            title = stringResource(Res.string.land_list_empty_title),
                            body = stringResource(Res.string.land_list_empty_body),
                            action = {
                                Button(onClick = onAddLand) {
                                    Text(stringResource(Res.string.land_list_add))
                                }
                            },
                        )

                        else -> LandListContent(
                            state = state,
                            wideWindow = wideWindow,
                            onAddLand = onAddLand,
                            onEditLand = onEditLand,
                            onRemoveLand = onRemoveLand,
                            onQueryChange = onQueryChange,
                        )
                    }
                }
            }
        }
    }
}

/**
 * The populated list: the summary of the shown set, the search field, the single full-width Add
 * action, then the matching rows or the no-results panel.
 *
 * The summary describes exactly the set the person is looking at: every saved land for a blank
 * query, only the matches otherwise. When nothing matches there is no summary, because a total for
 * zero shown lands could only be misread.
 */
@Composable
private fun LandListContent(
    state: LandListState,
    wideWindow: Boolean,
    onAddLand: () -> Unit,
    onEditLand: (Land) -> Unit,
    onRemoveLand: (Land) -> Unit,
    onQueryChange: (String) -> Unit,
) {
    // The Spanish labels live in strings.xml, so the screen resolves them once per composition and
    // hands them to the pure filter; a non-composable function may not read Res.string.
    val labels = landSearchLabels()
    val matches = filterLands(state.lands, state.query, labels)
    // The same rule the filter uses decides whether anything is described as filtered: a query of
    // punctuation or emoji only returns every land, so it must not switch the scope or the captions.
    val queryActive = hasSearchTokens(state.query)

    if (matches.isNotEmpty()) {
        LandSummarySection(
            summary = summarizeLands(matches),
            savedTotal = state.lands.size,
            filtered = queryActive,
            wideWindow = wideWindow,
        )
    }

    ManijeroSearchField(
        value = state.query,
        onValueChange = onQueryChange,
        label = stringResource(Res.string.land_search_label),
        clearDescription = stringResource(Res.string.land_search_clear),
        placeholder = stringResource(Res.string.land_search_hint),
    )

    Button(
        onClick = onAddLand,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(stringResource(Res.string.land_list_add))
    }

    if (matches.isEmpty()) {
        LandNoResults(onClearQuery = { onQueryChange("") })
    } else {
        matches.forEach { land ->
            LandRow(
                land = land,
                onEdit = { onEditLand(land) },
                onRemove = { onRemoveLand(land) },
            )
        }
    }
}

/**
 * The three annotated summary cards over a scope caption. Values are formatted by the accepted
 * `formatHectares`/`formatTreeCount`, an absent value reads `Sin datos` instead of a zero, and every
 * card carries the denominator caption of the set it counted. One column below the accepted
 * [WideWindowBreakpoint], three equal-width columns from it; the caller passes the window result so
 * the breakpoint is measured on the window, not on the capped content column.
 */
@Composable
private fun LandSummarySection(
    summary: LandSummary,
    savedTotal: Int,
    filtered: Boolean,
    wideWindow: Boolean,
    modifier: Modifier = Modifier,
) {
    // Each caption pluralizes on the denominator it prints, so its noun and any verb agree with the
    // number next to them: the count card prints the saved total, the surface/tree cards print the
    // shown land count (which is the match count while a query is active, as scenario 4 requires).
    // The search relation itself is stated by `land_summary_scope_filtered` above the cards; one
    // pluralized sentence carrying two different counts could not agree with both.
    val countDenominator = if (filtered) savedTotal else summary.total
    val shownDenominator = summary.total
    val countCaption = if (filtered) {
        pluralStringResource(
            resource = Res.plurals.land_summary_count_caption_filtered,
            quantity = countDenominator,
            summary.total,
            countDenominator,
        )
    } else {
        pluralStringResource(
            resource = Res.plurals.land_summary_count_caption,
            quantity = countDenominator,
        )
    }
    val surfaceCaption = pluralStringResource(
        resource = if (filtered) {
            Res.plurals.land_summary_surface_caption_filtered
        } else {
            Res.plurals.land_summary_surface_caption
        },
        quantity = shownDenominator,
        summary.surfaceKnownCount,
        shownDenominator,
    )
    val treeCaption = pluralStringResource(
        resource = if (filtered) {
            Res.plurals.land_summary_trees_caption_filtered
        } else {
            Res.plurals.land_summary_trees_caption
        },
        quantity = shownDenominator,
        summary.treeKnownCount,
        shownDenominator,
    )
    val surfaceValue = summary.surfaceTotal
        ?.let { total -> stringResource(Res.string.land_summary_surface_value, formatHectares(total)) }
        ?: stringResource(Res.string.land_summary_no_data)
    val treeValue = summary.treeTotal
        ?.let { total ->
            stringResource(
                resource = if (total == 1L) {
                    Res.string.land_summary_trees_value_one
                } else {
                    Res.string.land_summary_trees_value_other
                },
                formatTreeCount(total),
            )
        }
        ?: stringResource(Res.string.land_summary_no_data)

    val cards: List<@Composable (Modifier) -> Unit> = listOf(
        { cardModifier ->
            ManijeroStatCard(
                label = stringResource(Res.string.land_summary_count_label),
                value = formatTreeCount(summary.total),
                supporting = countCaption,
                modifier = cardModifier,
            )
        },
        { cardModifier ->
            ManijeroStatCard(
                label = stringResource(Res.string.land_summary_surface_label),
                value = surfaceValue,
                supporting = surfaceCaption,
                modifier = cardModifier,
            )
        },
        { cardModifier ->
            ManijeroStatCard(
                label = stringResource(Res.string.land_summary_trees_label),
                value = treeValue,
                supporting = treeCaption,
                modifier = cardModifier,
            )
        },
    )

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
    ) {
        ManijeroSectionHeader(
            title = stringResource(Res.string.land_summary_title),
            description = stringResource(
                if (filtered) {
                    Res.string.land_summary_scope_filtered
                } else {
                    Res.string.land_summary_scope_all
                },
            ),
            heading = true,
        )
        if (wideWindow) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
            ) {
                cards.forEach { card -> card(Modifier.weight(1f)) }
            }
        } else {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
            ) {
                cards.forEach { card -> card(Modifier.fillMaxWidth()) }
            }
        }
    }
}

/**
 * The honest no-results state: a neutral card, the plain sentence and one named clear action.
 *
 * It is a plain card, not a callout, so typing does not announce a live region on every keystroke.
 * The Add action stays above it and reachable.
 */
@Composable
private fun LandNoResults(
    onClearQuery: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ManijeroCard(modifier = modifier, tone = ManijeroCardTone.Tonal) {
        Text(
            text = stringResource(Res.string.land_search_no_results),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        TextButton(onClick = onClearQuery) {
            Text(stringResource(Res.string.land_search_clear))
        }
    }
}

/** The resolved Spanish search labels of every water, production and variety value. */
@Composable
private fun landSearchLabels(): LandSearchLabels = LandSearchLabels(
    waterRegime = WaterRegime.entries.associateWith { regime ->
        stringResource(waterRegimeLabel(regime))
    },
    productionMethod = ProductionMethod.entries.associateWith { method ->
        stringResource(productionMethodLabel(method))
    },
    variety = LandVariety.entries.associateWith { variety ->
        stringResource(landVarietyLabel(variety))
    },
)

/**
 * One saved land. The name and its details are merged into a single node so assistive technology
 * reads them together, while the `Editar` and `Eliminar` controls are their own labelled buttons
 * whose accessible description names the exact saved land. The row card itself is not clickable:
 * reading a row never navigates, and neither control writes anything by itself.
 */
@Composable
private fun LandRow(
    land: Land,
    onEdit: () -> Unit,
    onRemove: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLowest,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics(mergeDescendants = true) {},
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = land.name,
                    style = MaterialTheme.typography.titleMedium,
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
            val editDescription =
                stringResource(Res.string.land_list_edit_description, land.name)
            TextButton(
                onClick = onEdit,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics { contentDescription = editDescription },
            ) {
                Text(stringResource(Res.string.land_list_edit))
            }
            val removeDescription =
                stringResource(Res.string.land_list_remove_description, land.name)
            TextButton(
                onClick = onRemove,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics { contentDescription = removeDescription },
            ) {
                Text(stringResource(Res.string.land_list_remove))
            }
        }
    }
}

/**
 * The known detail lines of one land, shared by the list row, the removal confirmation and the
 * clarification chooser so a value reads the same everywhere. It renders no name, id or notes: the
 * caller shows the name itself. An absent municipality, surface or tree count is omitted, never
 * shown as zero or guessed; an `UNKNOWN` attribute reads `No lo sé`.
 */
@Suppress("LongParameterList")
@Composable
internal fun LandDetails(
    zone: String,
    municipality: String?,
    variety: LandVariety,
    varietyOther: String?,
    areaHectares: Double?,
    treeCount: Int?,
    waterRegime: WaterRegime,
    productionMethod: ProductionMethod,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        if (zone.isNotBlank()) {
            LandRowDetail(stringResource(Res.string.land_list_zone, zone))
        }
        municipality?.takeIf { it.isNotBlank() }?.let { value ->
            LandRowDetail(stringResource(Res.string.land_list_municipality, value))
        }
        val varietyValue = when (variety) {
            LandVariety.OTHER -> varietyOther?.takeIf { it.isNotBlank() }
                ?: stringResource(Res.string.add_land_variety_other)

            else -> stringResource(landVarietyLabel(variety))
        }
        LandRowDetail(stringResource(Res.string.land_list_variety, varietyValue))
        areaHectares?.let { value ->
            LandRowDetail(
                stringResource(Res.string.land_list_surface, formatHectares(value)),
            )
        }
        treeCount?.let { value ->
            LandRowDetail(stringResource(Res.string.land_list_trees, formatTreeCount(value)))
        }
        LandRowDetail(
            stringResource(
                Res.string.land_list_water,
                stringResource(waterRegimeLabel(waterRegime)),
            ),
        )
        LandRowDetail(
            stringResource(
                Res.string.land_list_production,
                stringResource(productionMethodLabel(productionMethod)),
            ),
        )
    }
}

@Composable
private fun LandRowDetail(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

/** Reuses the form's vocabulary so a value reads the same in the list as in the form. */
private fun waterRegimeLabel(waterRegime: WaterRegime): StringResource = when (waterRegime) {
    WaterRegime.UNKNOWN -> Res.string.add_land_unknown
    WaterRegime.DRYLAND -> Res.string.add_land_water_dryland
    WaterRegime.IRRIGATED -> Res.string.add_land_water_irrigated
    WaterRegime.MIXED -> Res.string.add_land_water_mixed
}

private fun productionMethodLabel(productionMethod: ProductionMethod): StringResource =
    when (productionMethod) {
        ProductionMethod.UNKNOWN -> Res.string.add_land_unknown
        ProductionMethod.CONVENTIONAL -> Res.string.add_land_production_conventional
        ProductionMethod.ORGANIC -> Res.string.add_land_production_organic
        ProductionMethod.MIXED -> Res.string.add_land_production_mixed
    }

@Suppress("LongParameterList")
private fun previewLand(
    id: String,
    name: String,
    zone: String = "El Llano",
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

@Preview(name = "Land list — empty")
@Composable
private fun LandListEmptyPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — two distinguishable lands")
@Composable
private fun LandListTwoLandsPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand(
                        "land-1",
                        "Los Olivos",
                        zone = "Camino de la Fuente",
                        municipality = "Martos",
                        variety = LandVariety.PICUAL,
                        areaHectares = 1.5,
                        treeCount = 85,
                        waterRegime = WaterRegime.DRYLAND,
                        productionMethod = ProductionMethod.ORGANIC,
                    ),
                    previewLand(
                        "land-2",
                        "La Loma",
                        zone = "Linde del arroyo",
                        municipality = "Úbeda",
                        variety = LandVariety.OTHER,
                        varietyOther = "Royal de Cazorla",
                        waterRegime = WaterRegime.IRRIGATED,
                    ),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — summary without data")
@Composable
private fun LandListSummaryWithoutDataPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand("land-1", "Los Olivos", treeCount = 1),
                    previewLand("land-2", "La Loma", municipality = "Martos"),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — filtered")
@Composable
private fun LandListFilteredPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand(
                        "land-1",
                        "Los Olivos",
                        municipality = "Martos",
                        areaHectares = 1.5,
                        treeCount = 85,
                    ),
                    previewLand(
                        "land-2",
                        "La Loma",
                        municipality = "Úbeda",
                        variety = LandVariety.OTHER,
                        varietyOther = "Royal de Cazorla",
                    ),
                ),
                query = "ubeda",
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — search without results")
@Composable
private fun LandListNoResultsPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand("land-1", "Los Olivos", municipality = "Martos"),
                    previewLand("land-2", "La Loma", municipality = "Úbeda"),
                ),
                query = "zzz",
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — duplicate names")
@Composable
private fun LandListDuplicateNamesPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand("land-1", "Los Olivos", zone = "El Llano"),
                    previewLand(
                        "land-2",
                        "Los Olivos",
                        zone = "Las Eras",
                        municipality = "Úbeda",
                        waterRegime = WaterRegime.DRYLAND,
                    ),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — many lands")
@Composable
private fun LandListManyLandsPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = (1..8).map { index ->
                    previewLand(
                        id = "land-$index",
                        name = "Terreno $index",
                        municipality = "Municipio $index",
                        waterRegime = WaterRegime.entries[index % WaterRegime.entries.size],
                        productionMethod = ProductionMethod.entries[
                            index % ProductionMethod.entries.size,
                        ],
                    )
                },
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — long text")
@Composable
private fun LandListLongTextPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand(
                        id = "land-1",
                        name = "El olivar de mi abuelo junto al camino de la fuente",
                        municipality = "Villanueva del Arzobispo (Sierra de Cazorla)",
                        waterRegime = WaterRegime.MIXED,
                        productionMethod = ProductionMethod.MIXED,
                    ),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — load failure")
@Composable
private fun LandListLoadFailurePreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(loadFailed = true),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — just saved")
@Composable
private fun LandListJustSavedPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(lands = listOf(previewLand("land-1", "Los Olivos"))),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
            confirmation = LandListConfirmation.ADDED,
        )
    }
}

@Preview(name = "Land list — just updated")
@Composable
private fun LandListJustUpdatedPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(lands = listOf(previewLand("land-1", "Los Olivos corregido"))),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
            confirmation = LandListConfirmation.UPDATED,
        )
    }
}

@Preview(name = "Land list — just removed")
@Composable
private fun LandListJustRemovedPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(lands = listOf(previewLand("land-2", "La Loma"))),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
            confirmation = LandListConfirmation.REMOVED,
        )
    }
}

@Preview(name = "Land list — compact", widthDp = 320)
@Composable
private fun LandListCompactPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(lands = listOf(previewLand("land-1", "Los Olivos"))),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — wide", widthDp = 900)
@Composable
private fun LandListWidePreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(previewLand("land-1", "La Loma", municipality = "Martos")),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}

@Preview(name = "Land list — large font", fontScale = 2f)
@Composable
private fun LandListLargeFontPreview() {
    ManijeroTheme {
        LandListScreen(
            state = LandListState(
                lands = listOf(
                    previewLand(
                        "land-1",
                        "Los Olivos",
                        waterRegime = WaterRegime.IRRIGATED,
                        productionMethod = ProductionMethod.ORGANIC,
                    ),
                ),
            ),
            onAddLand = {},
            onEditLand = {},
            onRemoveLand = {},
            onRetry = {},
            onQueryChange = {},
        )
    }
}
