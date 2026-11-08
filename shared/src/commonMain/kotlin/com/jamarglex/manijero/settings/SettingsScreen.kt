package com.jamarglex.manijero.settings

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.design.ManijeroScreen
import com.jamarglex.manijero.design.ManijeroSectionHeader
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroShapes
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.nav_help
import manijero.shared.generated.resources.settings_backup_description
import manijero.shared.generated.resources.settings_backup_title
import manijero.shared.generated.resources.settings_help_description
import manijero.shared.generated.resources.settings_improvement_detail_1
import manijero.shared.generated.resources.settings_improvement_detail_2
import manijero.shared.generated.resources.settings_improvement_detail_3
import manijero.shared.generated.resources.settings_improvement_detail_4
import manijero.shared.generated.resources.settings_improvement_switch
import manijero.shared.generated.resources.settings_improvement_title
import manijero.shared.generated.resources.settings_intro
import manijero.shared.generated.resources.settings_title
import org.jetbrains.compose.resources.stringResource

/**
 * The `Ajustes` tab: one heading, a short explanation, then in order the `Ayúdanos a mejorar`
 * section, `Copia en un archivo` and `Ayuda`, each place it leads to as one tappable row.
 * `Ayuda` is always offered; `Copia en un archivo` only when the host wires [onOpenBackup] (a local
 * land store and a platform file picker exist). The screen owns no state and no copy beyond its rows.
 */
@Composable
internal fun SettingsScreen(
    onOpenHelp: () -> Unit,
    improvementEnabled: Boolean,
    onImprovementChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
    onOpenBackup: (() -> Unit)? = null,
) {
    ManijeroScreen(modifier = modifier) {
        Column(verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small)) {
            Text(
                text = stringResource(Res.string.settings_title),
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.semantics { heading() },
            )
            Text(
                text = stringResource(Res.string.settings_intro),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        ImprovementSection(enabled = improvementEnabled, onChange = onImprovementChange)
        if (onOpenBackup != null) {
            SettingsRow(
                title = stringResource(Res.string.settings_backup_title),
                description = stringResource(Res.string.settings_backup_description),
                onClick = onOpenBackup,
            )
        }
        SettingsRow(
            title = stringResource(Res.string.nav_help),
            description = stringResource(Res.string.settings_help_description),
            onClick = onOpenHelp,
        )
    }
}

/**
 * The `Ayúdanos a mejorar` section: the one place that explains the standing permission to keep
 * sent questions and answers. The labelled row is one switch target (announced as a switch with its
 * state, at least 48 dp); the plain lines below state that it starts off, what is and is never kept,
 * that it stays on until turned off, and the 30-day deletion. Nothing here is colour-only.
 */
@Composable
private fun ImprovementSection(enabled: Boolean, onChange: (Boolean) -> Unit) {
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        ManijeroSectionHeader(
            title = stringResource(Res.string.settings_improvement_title),
            heading = true,
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = ManijeroLayout.MinTouchTarget)
                .toggleable(value = enabled, role = Role.Switch, onValueChange = onChange),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
        ) {
            Text(
                text = stringResource(Res.string.settings_improvement_switch),
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.weight(1f),
            )
            Switch(checked = enabled, onCheckedChange = null)
        }
        listOf(
            Res.string.settings_improvement_detail_1,
            Res.string.settings_improvement_detail_2,
            Res.string.settings_improvement_detail_3,
            Res.string.settings_improvement_detail_4,
        ).forEach { line ->
            Text(
                text = stringResource(line),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * One settings entry: a whole-card button (one merged node announced as a button with its title and
 * description) with a 24 dp radius, a 1 dp `outlineVariant` boundary and at least a 48 dp target.
 */
@Composable
private fun SettingsRow(
    title: String,
    description: String,
    onClick: () -> Unit,
) {
    Surface(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = ManijeroLayout.MinTouchTarget)
            .semantics(mergeDescendants = true) { role = Role.Button },
        shape = ManijeroShapes.Large,
        color = MaterialTheme.colorScheme.surfaceContainerLowest,
        contentColor = MaterialTheme.colorScheme.onSurface,
        border = BorderStroke(ManijeroLayout.BorderWidth, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            modifier = Modifier.padding(ManijeroSpacing.Comfortable),
            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
        ) {
            Text(text = title, style = MaterialTheme.typography.titleMedium)
            Text(
                text = description,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Preview(name = "Ajustes — claro")
@Composable
private fun SettingsLightPreview() {
    ManijeroTheme(darkTheme = false) { SettingsScreen(onOpenHelp = {}, improvementEnabled = false, onImprovementChange = {}, onOpenBackup = {}) }
}

@Preview(name = "Ajustes — oscuro")
@Composable
private fun SettingsDarkPreview() {
    ManijeroTheme(darkTheme = true) { SettingsScreen(onOpenHelp = {}, improvementEnabled = false, onImprovementChange = {}, onOpenBackup = {}) }
}

@Preview(name = "Ajustes — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun SettingsLargeTextPreview() {
    ManijeroTheme(darkTheme = false) { SettingsScreen(onOpenHelp = {}, improvementEnabled = false, onImprovementChange = {}, onOpenBackup = {}) }
}
