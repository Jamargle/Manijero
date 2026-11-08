package com.jamarglex.manijero.settings

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.design.ManijeroScreen
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroShapes
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.nav_help
import manijero.shared.generated.resources.settings_backup_description
import manijero.shared.generated.resources.settings_backup_title
import manijero.shared.generated.resources.settings_help_description
import manijero.shared.generated.resources.settings_intro
import manijero.shared.generated.resources.settings_title
import org.jetbrains.compose.resources.stringResource

/**
 * The `Ajustes` tab: one heading, a short explanation, and one tappable row per place it leads to.
 * `Ayuda` is always offered; `Copia en un archivo` only when the host wires [onOpenBackup] (a local
 * land store and a platform file picker exist). The screen owns no state and no copy beyond its rows.
 */
@Composable
internal fun SettingsScreen(
    onOpenHelp: () -> Unit,
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
        SettingsRow(
            title = stringResource(Res.string.nav_help),
            description = stringResource(Res.string.settings_help_description),
            onClick = onOpenHelp,
        )
        if (onOpenBackup != null) {
            SettingsRow(
                title = stringResource(Res.string.settings_backup_title),
                description = stringResource(Res.string.settings_backup_description),
                onClick = onOpenBackup,
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
    ManijeroTheme(darkTheme = false) { SettingsScreen(onOpenHelp = {}, onOpenBackup = {}) }
}

@Preview(name = "Ajustes — oscuro")
@Composable
private fun SettingsDarkPreview() {
    ManijeroTheme(darkTheme = true) { SettingsScreen(onOpenHelp = {}, onOpenBackup = {}) }
}

@Preview(name = "Ajustes — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun SettingsLargeTextPreview() {
    ManijeroTheme(darkTheme = false) { SettingsScreen(onOpenHelp = {}, onOpenBackup = {}) }
}
