package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.ic_add
import manijero.shared.generated.resources.ic_back
import manijero.shared.generated.resources.ic_chat
import manijero.shared.generated.resources.ic_check
import manijero.shared.generated.resources.ic_chevron_down
import manijero.shared.generated.resources.ic_clear
import manijero.shared.generated.resources.ic_delete
import manijero.shared.generated.resources.ic_edit
import manijero.shared.generated.resources.ic_external_link
import manijero.shared.generated.resources.ic_help
import manijero.shared.generated.resources.ic_info
import manijero.shared.generated.resources.ic_lands
import manijero.shared.generated.resources.ic_retry
import manijero.shared.generated.resources.ic_search
import manijero.shared.generated.resources.ic_send
import manijero.shared.generated.resources.ic_warning
import org.jetbrains.compose.resources.DrawableResource

/** One glyph and the review identifier printed under it. The label is not shipped copy. */
private data class BoardGlyph(val label: String, val resource: DrawableResource)

/** The sixteen icons in spec order, each labelled with its resource name for the reviewer. */
private val boardGlyphs = listOf(
    BoardGlyph("ic_chat", Res.drawable.ic_chat),
    BoardGlyph("ic_lands", Res.drawable.ic_lands),
    BoardGlyph("ic_help", Res.drawable.ic_help),
    BoardGlyph("ic_search", Res.drawable.ic_search),
    BoardGlyph("ic_add", Res.drawable.ic_add),
    BoardGlyph("ic_edit", Res.drawable.ic_edit),
    BoardGlyph("ic_delete", Res.drawable.ic_delete),
    BoardGlyph("ic_back", Res.drawable.ic_back),
    BoardGlyph("ic_retry", Res.drawable.ic_retry),
    BoardGlyph("ic_send", Res.drawable.ic_send),
    BoardGlyph("ic_external_link", Res.drawable.ic_external_link),
    BoardGlyph("ic_info", Res.drawable.ic_info),
    BoardGlyph("ic_warning", Res.drawable.ic_warning),
    BoardGlyph("ic_check", Res.drawable.ic_check),
    BoardGlyph("ic_chevron_down", Res.drawable.ic_chevron_down),
    BoardGlyph("ic_clear", Res.drawable.ic_clear),
)

/**
 * Review-only board for the brand vectors: the mark at 28/32/48 dp, the illustration at 160/200 dp,
 * all sixteen icons at 24 dp, and two icons at the inline 20 dp.
 *
 * It exists so the Desktop and Android host screenshot suites can prove that every vector decodes
 * and takes its colour from the theme in both appearances. No screen references it, its labels are
 * review identifiers rather than shipped copy, and rendering it is not an accessibility, usability,
 * or device claim.
 */
@Composable
internal fun BrandVectorBoard() {
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
        contentColor = MaterialTheme.colorScheme.onBackground,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(ManijeroSpacing.Medium),
            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Comfortable),
        ) {
            Text(
                text = "Vectores de marca",
                style = MaterialTheme.typography.headlineSmall,
            )
            Text(
                text = "Tablero solo para revisión: no forma parte de ninguna pantalla.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            BoardSection("Marca — 28, 32 y 48 dp") {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Comfortable),
                    verticalAlignment = Alignment.Bottom,
                ) {
                    listOf(28, 32, 48).forEach { sizeDp ->
                        BoardCell(label = "$sizeDp dp") { ManijeroBrandMark(size = sizeDp.dp) }
                    }
                }
            }

            BoardSection("Ilustración — 160 y 200 dp") {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Comfortable),
                    verticalAlignment = Alignment.Bottom,
                ) {
                    listOf(160, 200).forEach { sizeDp ->
                        BoardCell(label = "$sizeDp dp") { ManijeroOliveBranch(size = sizeDp.dp) }
                    }
                }
            }

            BoardSection("Iconos — 24 dp") {
                Column(verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small)) {
                    boardGlyphs.chunked(4).forEach { rowGlyphs ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact),
                            verticalAlignment = Alignment.Bottom,
                        ) {
                            rowGlyphs.forEach { glyph ->
                                BoardCell(label = glyph.label, modifier = Modifier.weight(1f)) {
                                    ManijeroIcon(
                                        resource = glyph.resource,
                                        contentDescription = null,
                                        size = ManijeroIconSize.Default,
                                    )
                                }
                            }
                        }
                    }
                }
            }

            BoardSection("Iconos — 20 dp (en línea)") {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact),
                    verticalAlignment = Alignment.Bottom,
                ) {
                    listOf(
                        BoardGlyph("ic_search", Res.drawable.ic_search),
                        BoardGlyph("ic_clear", Res.drawable.ic_clear),
                    ).forEach { glyph ->
                        BoardCell(label = glyph.label, modifier = Modifier.width(96.dp)) {
                            ManijeroIcon(
                                resource = glyph.resource,
                                contentDescription = null,
                                size = ManijeroIconSize.Inline,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun BoardSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact)) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.onBackground,
        )
        content()
    }
}

@Composable
private fun BoardCell(
    label: String,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
    ) {
        content()
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            maxLines = 1,
        )
    }
}

@Preview(name = "Vectores de marca — claro", widthDp = 900, heightDp = 1200)
@Composable
private fun BrandVectorBoardLightPreview() {
    ManijeroTheme(darkTheme = false) { BrandVectorBoard() }
}

@Preview(name = "Vectores de marca — oscuro", widthDp = 900, heightDp = 1200)
@Composable
private fun BrandVectorBoardDarkPreview() {
    ManijeroTheme(darkTheme = true) { BrandVectorBoard() }
}
