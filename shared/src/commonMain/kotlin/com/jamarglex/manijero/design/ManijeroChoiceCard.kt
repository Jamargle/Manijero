package com.jamarglex.manijero.design

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectable
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroShapes
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme

/**
 * One radio option as a large selection card: a `RadioButton` plus the caller's [label], with the
 * `Role.RadioButton` role and the selected state coming from a single `selectable` on the card.
 *
 * [optionDescription] lets the caller merge the option's group into the announced name (for example
 * "Riego: No lo sé"), which keeps two identically worded options distinguishable. Grouping
 * (`Modifier.selectableGroup()`) stays the caller's responsibility, and the component never hides an
 * option. [isError] adds the error boundary; the caller pairs it with its own visible error text.
 */
@Composable
internal fun ManijeroChoiceCard(
    label: String,
    selected: Boolean,
    onSelect: () -> Unit,
    modifier: Modifier = Modifier,
    optionDescription: String? = null,
    isError: Boolean = false,
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = ManijeroLayout.MinTouchTarget)
            .selectable(
                selected = selected,
                role = Role.RadioButton,
                onClick = onSelect,
            )
            .semantics(mergeDescendants = true) {
                if (optionDescription != null) contentDescription = optionDescription
            },
        shape = ManijeroShapes.Large,
        color = MaterialTheme.colorScheme.surfaceContainerLowest,
        contentColor = MaterialTheme.colorScheme.onSurface,
        border = BorderStroke(
            ManijeroLayout.BorderWidth,
            if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.outlineVariant,
        ),
    ) {
        Row(
            modifier = Modifier.padding(
                horizontal = ManijeroSpacing.Small,
                vertical = ManijeroSpacing.Small,
            ),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            RadioButton(selected = selected, onClick = null)
            Text(
                text = label,
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(start = ManijeroSpacing.Small),
            )
        }
    }
}

@Composable
private fun ManijeroChoiceCardPreviewContent() {
    Column(verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact)) {
        ManijeroChoiceCard(
            label = "No lo sé",
            selected = true,
            onSelect = {},
            optionDescription = "Riego: No lo sé",
        )
        ManijeroChoiceCard(
            label = "Secano",
            selected = false,
            onSelect = {},
            optionDescription = "Riego: Secano",
        )
        ManijeroChoiceCard(
            label = "Regadío",
            selected = false,
            onSelect = {},
            optionDescription = "Riego: Regadío",
            isError = true,
        )
    }
}

@Composable
private fun ManijeroChoiceCardPreviewFrame(dark: Boolean) {
    ManijeroTheme(darkTheme = dark) {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ManijeroSpacing.Small),
            ) { ManijeroChoiceCardPreviewContent() }
        }
    }
}

@Preview(name = "ManijeroChoiceCard — claro", widthDp = 380)
@Composable
private fun ManijeroChoiceCardLightPreview() = ManijeroChoiceCardPreviewFrame(dark = false)

@Preview(name = "ManijeroChoiceCard — oscuro", widthDp = 380)
@Composable
private fun ManijeroChoiceCardDarkPreview() = ManijeroChoiceCardPreviewFrame(dark = true)

@Preview(name = "ManijeroChoiceCard — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun ManijeroChoiceCardLargeTextPreview() = ManijeroChoiceCardPreviewFrame(dark = false)
