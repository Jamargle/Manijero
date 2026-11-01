package com.jamarglex.manijero.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.platform.testTag
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.design.ManijeroIcon
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroShapes
import com.jamarglex.manijero.theme.ManijeroSpacing
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.chat_source_excerpt_label
import manijero.shared.generated.resources.chat_source_issuing_body
import manijero.shared.generated.resources.chat_source_label
import manijero.shared.generated.resources.chat_source_link_unavailable
import manijero.shared.generated.resources.chat_source_location
import manijero.shared.generated.resources.chat_source_open
import manijero.shared.generated.resources.chat_source_open_description
import manijero.shared.generated.resources.chat_source_section_title
import manijero.shared.generated.resources.chat_source_verified_on
import manijero.shared.generated.resources.ic_external_link
import org.jetbrains.compose.resources.stringResource

/**
 * The cited sources of one answered reply, in payload order. The heading and one card per source
 * are rendered under the answer; nothing is reordered, merged, or deduplicated.
 */
@Composable
internal fun SourceCardsSection(cards: List<SourceCard>, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
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
 * control is a separate focusable button whose accessible description names the source. When the
 * URL is not openable, the pinned unavailability line is shown instead and no control is offered.
 *
 * The card is the accepted outlined container; the source number stays a labelled text line rather
 * than a land-attribute chip, so a citation number can never read as a land status.
 */
@Composable
private fun SourceCardView(card: SourceCard, modifier: Modifier = Modifier) {
    ManijeroCard(modifier = modifier.testTag(ChatTestTags.SOURCE_CARD), tone = ManijeroCardTone.Outlined) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .semantics(mergeDescendants = true) {},
            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact),
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
                shape = ManijeroShapes.Medium,
                color = MaterialTheme.colorScheme.surfaceVariant,
            ) {
                Column(
                    modifier = Modifier.padding(ManijeroSpacing.Small),
                    verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
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
            // One best-effort open: the platform URI handler is the only path, and a platform that
            // refuses (e.g. Desktop without AWT BROWSE support) must never crash the screen.
            val uriHandler = LocalUriHandler.current
            val openDescription = stringResource(Res.string.chat_source_open_description, card.title)
            Button(
                onClick = { runCatching { uriHandler.openUri(link) } },
                modifier = Modifier.semantics { contentDescription = openDescription },
            ) {
                ManijeroIcon(
                    resource = Res.drawable.ic_external_link,
                    contentDescription = null,
                    size = ManijeroIconSize.Inline,
                )
                Spacer(modifier = Modifier.width(ManijeroSpacing.Compact))
                Text(stringResource(Res.string.chat_source_open))
            }
        } else {
            SourceCardDetail(stringResource(Res.string.chat_source_link_unavailable))
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
