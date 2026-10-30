package com.jamarglex.manijero.lands

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.design.ManijeroCallout
import com.jamarglex.manijero.design.ManijeroCalloutTone
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.design.ManijeroScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.land_backup_back
import manijero.shared.generated.resources.land_backup_cancel
import manijero.shared.generated.resources.land_backup_damaged
import manijero.shared.generated.resources.land_backup_description
import manijero.shared.generated.resources.land_backup_export_action
import manijero.shared.generated.resources.land_backup_export_failed
import manijero.shared.generated.resources.land_backup_export_title
import manijero.shared.generated.resources.land_backup_exported
import manijero.shared.generated.resources.land_backup_import_action
import manijero.shared.generated.resources.land_backup_import_body
import manijero.shared.generated.resources.land_backup_import_title
import manijero.shared.generated.resources.land_backup_invalid_content
import manijero.shared.generated.resources.land_backup_not_a_backup
import manijero.shared.generated.resources.land_backup_open_failed
import manijero.shared.generated.resources.land_backup_preview_active
import manijero.shared.generated.resources.land_backup_preview_none
import manijero.shared.generated.resources.land_backup_preview_old_copy
import manijero.shared.generated.resources.land_backup_preview_removed
import manijero.shared.generated.resources.land_backup_preview_replace_body
import manijero.shared.generated.resources.land_backup_preview_replace_title
import manijero.shared.generated.resources.land_backup_preview_title
import manijero.shared.generated.resources.land_backup_replace_action
import manijero.shared.generated.resources.land_backup_restore_failed
import manijero.shared.generated.resources.land_backup_restored
import manijero.shared.generated.resources.land_backup_store_unreadable
import manijero.shared.generated.resources.land_backup_title
import manijero.shared.generated.resources.land_backup_too_large
import manijero.shared.generated.resources.land_backup_unsupported_version
import manijero.shared.generated.resources.land_backup_warning_body
import manijero.shared.generated.resources.land_backup_warning_title
import manijero.shared.generated.resources.land_backup_working
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource

/**
 * The `Copia en un archivo` screen: save every land (active and removed) to a portable file, or
 * restore them from one.
 *
 * It renders whatever [state] it receives and reports every interaction through its callbacks; the
 * picker, the validation, and the store live in [LandBackupController]. The unencrypted-file warning
 * is always visible above both actions. A chosen file is shown as a preview (counts and names of both
 * lists) with the replace-all consequence spelled out, and only the explicit
 * `Sustituir todos mis terrenos` action writes anything. Every message is a polite live region and
 * carries words, never colour alone.
 */
@Composable
fun LandBackupScreen(
    state: LandBackupState,
    onExport: () -> Unit,
    onChooseFile: () -> Unit,
    onConfirmRestore: () -> Unit,
    onCancelPreview: () -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ManijeroScreen(modifier = modifier) {
        Text(
            text = stringResource(Res.string.land_backup_title),
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.semantics { heading() },
        )
        Text(
            text = stringResource(Res.string.land_backup_description),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        ManijeroCallout(
            title = stringResource(Res.string.land_backup_warning_title),
            text = stringResource(Res.string.land_backup_warning_body),
            tone = ManijeroCalloutTone.Caution,
        )

        state.notice?.let { notice -> LandBackupNoticeCallout(notice) }

        if (state.working) {
            Text(
                text = stringResource(Res.string.land_backup_working),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics { liveRegion = LiveRegionMode.Polite },
            )
        }

        val preview = state.preview
        if (preview != null) {
            LandBackupPreviewSection(
                preview = preview,
                enabled = !state.working,
                onConfirmRestore = onConfirmRestore,
                onCancelPreview = onCancelPreview,
            )
        } else {
            LandBackupActions(
                enabled = !state.working,
                onExport = onExport,
                onChooseFile = onChooseFile,
            )
        }

        TextButton(onClick = onBack, enabled = !state.working, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(Res.string.land_backup_back))
        }
    }
}

@Composable
private fun LandBackupActions(
    enabled: Boolean,
    onExport: () -> Unit,
    onChooseFile: () -> Unit,
) {
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        Text(
            text = stringResource(Res.string.land_backup_export_title),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.semantics { heading() },
        )
        Button(onClick = onExport, enabled = enabled, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(Res.string.land_backup_export_action))
        }
    }
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        Text(
            text = stringResource(Res.string.land_backup_import_title),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.semantics { heading() },
        )
        Text(
            text = stringResource(Res.string.land_backup_import_body),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedButton(onClick = onChooseFile, enabled = enabled, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(Res.string.land_backup_import_action))
        }
    }
}

@Composable
private fun LandBackupPreviewSection(
    preview: LandBackupPreview,
    enabled: Boolean,
    onConfirmRestore: () -> Unit,
    onCancelPreview: () -> Unit,
) {
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        Text(
            text = stringResource(Res.string.land_backup_preview_title),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.semantics { heading() },
        )
        LandBackupNameList(
            heading = stringResource(Res.string.land_backup_preview_active, preview.backup.active.size),
            names = preview.backup.active.map { it.name },
        )
        LandBackupNameList(
            heading = stringResource(Res.string.land_backup_preview_removed, preview.backup.removed.size),
            names = preview.backup.removed.map { it.land.name },
        )
    }
    ManijeroCallout(
        title = stringResource(Res.string.land_backup_preview_replace_title),
        text = stringResource(
            Res.string.land_backup_preview_replace_body,
            preview.currentActiveCount,
            preview.currentRemovedCount,
        ),
        tone = ManijeroCalloutTone.Danger,
    )
    Text(
        text = stringResource(Res.string.land_backup_preview_old_copy),
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Button(
            onClick = onConfirmRestore,
            enabled = enabled,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.error,
                contentColor = MaterialTheme.colorScheme.onError,
            ),
        ) {
            Text(stringResource(Res.string.land_backup_replace_action))
        }
        TextButton(onClick = onCancelPreview, enabled = enabled, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(Res.string.land_backup_cancel))
        }
    }
}

/** One count line plus the names it counts, merged so a screen reader reads them together. */
@Composable
private fun LandBackupNameList(heading: String, names: List<String>) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {},
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            text = heading,
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.onSurface,
        )
        val lines = names.ifEmpty { listOf(stringResource(Res.string.land_backup_preview_none)) }
        lines.forEach { name ->
            Text(
                text = name,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun LandBackupNoticeCallout(notice: LandBackupNotice) {
    val (resource, tone) = noticeCopy(notice)
    ManijeroCallout(text = stringResource(resource), tone = tone)
}

private fun noticeCopy(notice: LandBackupNotice): Pair<StringResource, ManijeroCalloutTone> =
    when (notice) {
        LandBackupNotice.EXPORTED -> Res.string.land_backup_exported to ManijeroCalloutTone.Confirmation
        LandBackupNotice.RESTORED -> Res.string.land_backup_restored to ManijeroCalloutTone.Confirmation
        LandBackupNotice.EXPORT_FAILED -> Res.string.land_backup_export_failed to ManijeroCalloutTone.Danger
        LandBackupNotice.STORE_UNREADABLE -> Res.string.land_backup_store_unreadable to ManijeroCalloutTone.Danger
        LandBackupNotice.OPEN_FAILED -> Res.string.land_backup_open_failed to ManijeroCalloutTone.Danger
        LandBackupNotice.FILE_TOO_LARGE -> Res.string.land_backup_too_large to ManijeroCalloutTone.Danger
        LandBackupNotice.NOT_A_BACKUP -> Res.string.land_backup_not_a_backup to ManijeroCalloutTone.Danger
        LandBackupNotice.UNSUPPORTED_VERSION ->
            Res.string.land_backup_unsupported_version to ManijeroCalloutTone.Danger
        LandBackupNotice.DAMAGED -> Res.string.land_backup_damaged to ManijeroCalloutTone.Danger
        LandBackupNotice.INVALID_CONTENT -> Res.string.land_backup_invalid_content to ManijeroCalloutTone.Danger
        LandBackupNotice.RESTORE_FAILED -> Res.string.land_backup_restore_failed to ManijeroCalloutTone.Danger
    }

private fun previewBackupLand(id: String, name: String) = Land(
    id = id,
    name = name,
    zone = "El Llano",
    createdAtEpochMillis = 0,
    updatedAtEpochMillis = 0,
)

@Preview(name = "Land backup — start")
@Composable
private fun LandBackupStartPreview() {
    ManijeroTheme {
        LandBackupScreen(
            state = LandBackupState(),
            onExport = {}, onChooseFile = {}, onConfirmRestore = {}, onCancelPreview = {}, onBack = {},
        )
    }
}

@Preview(name = "Land backup — preview before replace")
@Composable
private fun LandBackupPreviewPreview() {
    ManijeroTheme {
        LandBackupScreen(
            state = LandBackupState(
                preview = LandBackupPreview(
                    backup = LandSnapshot(
                        active = listOf(previewBackupLand("a", "Los Olivos"), previewBackupLand("b", "La Loma")),
                        removed = listOf(RemovedLand(previewBackupLand("c", "El Cerro"), 0)),
                    ),
                    currentActiveCount = 1,
                    currentRemovedCount = 0,
                ),
            ),
            onExport = {}, onChooseFile = {}, onConfirmRestore = {}, onCancelPreview = {}, onBack = {},
        )
    }
}

@Preview(name = "Land backup — damaged file", fontScale = 2f)
@Composable
private fun LandBackupDamagedPreview() {
    ManijeroTheme(darkTheme = true) {
        LandBackupScreen(
            state = LandBackupState(notice = LandBackupNotice.DAMAGED),
            onExport = {}, onChooseFile = {}, onConfirmRestore = {}, onCancelPreview = {}, onBack = {},
        )
    }
}
