package com.jamarglex.manijero.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.platform.testTag
import com.jamarglex.manijero.ChatHomeAction
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.lands.Land
import com.jamarglex.manijero.lands.LandDetails
import com.jamarglex.manijero.theme.ManijeroSpacing
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.chat_home_clarification_continue
import manijero.shared.generated.resources.chat_home_clarification_description
import manijero.shared.generated.resources.chat_home_clarification_no_lands
import manijero.shared.generated.resources.chat_home_clarification_title
import org.jetbrains.compose.resources.stringResource

/**
 * The land chooser shown while a clarification is pending. It lists each offered land by its saved
 * name and known attributes (reused from the accepted land strings) with a multi-select checkbox,
 * and one primary `Continuar` enabled only once at least one land is selected. Nothing is renamed,
 * reordered, or invented: the list is already filtered to the service's opaque ids and the local
 * store's order.
 *
 * [lands] is `null` while the guarded local read has not resolved yet, so only the title and the
 * explanation show and the "cannot show your lands" fallback can never flash before the read
 * answers. A resolved list with no matching land (or a failed read) shows that fallback and no
 * control, so a land can never be fabricated.
 *
 * Each row is one merged-semantics checkbox control (label + details + checked state, never colour
 * alone) and the whole control meets the large-target guidance.
 */
@Composable
internal fun LandClarificationChooser(
    lands: List<Land>?,
    landIdsToChoose: List<String>,
    onAction: (ChatHomeAction) -> Unit,
    modifier: Modifier = Modifier,
) {
    var selectedIds by remember(landIdsToChoose) { mutableStateOf(emptySet<String>()) }
    ManijeroCard(
        modifier = modifier.fillMaxWidth().testTag(ChatTestTags.LAND_CLARIFICATION),
        tone = ManijeroCardTone.Outlined,
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
                            .padding(vertical = ManijeroSpacing.Small),
                        // A land block is several lines tall: centring the box would put it beside a
                        // detail line and away from the name it selects. The visual box is centred
                        // in its 48 dp target, so shift that target up to meet the first text line;
                        // the target itself stays 48 dp.
                        verticalAlignment = Alignment.Top,
                    ) {
                        Checkbox(
                            checked = checked,
                            onCheckedChange = null,
                            modifier = Modifier.offset(y = -ManijeroSpacing.Small),
                        )
                        Column(
                            modifier = Modifier.padding(start = ManijeroSpacing.Small),
                            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
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
