package com.jamarglex.manijero.connection

import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.design.ManijeroCallout
import com.jamarglex.manijero.design.ManijeroCalloutTone
import com.jamarglex.manijero.design.ManijeroScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.connection_address_example
import manijero.shared.generated.resources.connection_address_label
import manijero.shared.generated.resources.connection_back
import manijero.shared.generated.resources.connection_check
import manijero.shared.generated.resources.connection_checking
import manijero.shared.generated.resources.connection_in_use_default
import manijero.shared.generated.resources.connection_in_use_saved
import manijero.shared.generated.resources.connection_intro
import manijero.shared.generated.resources.connection_invalid
import manijero.shared.generated.resources.connection_not_manijero
import manijero.shared.generated.resources.connection_not_ready
import manijero.shared.generated.resources.connection_ready
import manijero.shared.generated.resources.connection_ready_unknown
import manijero.shared.generated.resources.connection_reset
import manijero.shared.generated.resources.connection_reset_done
import manijero.shared.generated.resources.connection_storage_failed
import manijero.shared.generated.resources.connection_title
import manijero.shared.generated.resources.connection_unreachable
import org.jetbrains.compose.resources.stringResource

/**
 * The test-build `Conexión` screen: type the answer-service address, press `Comprobar`, and read a
 * plain-Spanish result. It renders whatever [state] it receives and reports every interaction
 * through its callbacks; validation, the store, and the probe live in [ConnectionController].
 *
 * The typed text stays in the field after an error. Every result is a callout with an icon and
 * words, never colour alone, and the callout is the polite live region.
 */
@Composable
fun ConnectionScreen(
    state: ConnectionState,
    onInputChange: (String) -> Unit,
    onCheck: () -> Unit,
    onReset: () -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ManijeroScreen(modifier = modifier) {
        Text(
            text = stringResource(Res.string.connection_title),
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.semantics { heading() },
        )
        Text(
            text = stringResource(Res.string.connection_intro),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedTextField(
            value = state.input,
            onValueChange = onInputChange,
            modifier = Modifier.fillMaxWidth(),
            label = { Text(stringResource(Res.string.connection_address_label)) },
            supportingText = { Text(stringResource(Res.string.connection_address_example)) },
            singleLine = true,
            keyboardOptions = KeyboardOptions(
                autoCorrectEnabled = false,
                keyboardType = KeyboardType.Uri,
                imeAction = ImeAction.Done,
            ),
            keyboardActions = KeyboardActions(onDone = { if (!state.checking) onCheck() }),
        )
        Text(
            text = stringResource(
                when (state.activeSource) {
                    ServiceAddressSource.Default -> Res.string.connection_in_use_default
                    ServiceAddressSource.Saved -> Res.string.connection_in_use_saved
                },
                state.activeUrl,
            ),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        if (state.checking) {
            ManijeroCallout(
                text = stringResource(Res.string.connection_checking),
                tone = ManijeroCalloutTone.Info,
            )
        }
        state.notice?.let { notice -> ConnectionNoticeCallout(notice, state.activeUrl) }

        Button(onClick = onCheck, enabled = !state.checking, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(Res.string.connection_check))
        }
        TextButton(onClick = onReset, enabled = !state.checking, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(Res.string.connection_reset))
        }
        TextButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(Res.string.connection_back))
        }
    }
}

@Composable
private fun ConnectionNoticeCallout(notice: ConnectionNotice, activeUrl: String) {
    val text = when (notice) {
        ConnectionNotice.READY -> stringResource(Res.string.connection_ready)
        ConnectionNotice.NOT_READY -> stringResource(Res.string.connection_not_ready)
        ConnectionNotice.READY_UNKNOWN -> stringResource(Res.string.connection_ready_unknown)
        ConnectionNotice.UNREACHABLE -> stringResource(Res.string.connection_unreachable)
        ConnectionNotice.NOT_MANIJERO -> stringResource(Res.string.connection_not_manijero)
        ConnectionNotice.INVALID_ADDRESS -> stringResource(Res.string.connection_invalid)
        ConnectionNotice.STORAGE_FAILED -> stringResource(Res.string.connection_storage_failed)
        ConnectionNotice.RESET_TO_DEFAULT -> stringResource(Res.string.connection_reset_done, activeUrl)
    }
    ManijeroCallout(text = text, tone = notice.tone())
}

private fun ConnectionNotice.tone(): ManijeroCalloutTone = when (this) {
    ConnectionNotice.READY -> ManijeroCalloutTone.Confirmation
    ConnectionNotice.RESET_TO_DEFAULT -> ManijeroCalloutTone.Info
    ConnectionNotice.NOT_READY,
    ConnectionNotice.READY_UNKNOWN,
    -> ManijeroCalloutTone.Caution
    ConnectionNotice.UNREACHABLE,
    ConnectionNotice.NOT_MANIJERO,
    ConnectionNotice.INVALID_ADDRESS,
    ConnectionNotice.STORAGE_FAILED,
    -> ManijeroCalloutTone.Danger
}

private const val PREVIEW_DEFAULT_URL = "http://10.0.2.2:8000"
private const val PREVIEW_SAVED_URL = "http://192.168.1.20:8000"

@Composable
private fun ConnectionPreview(state: ConnectionState, darkTheme: Boolean = false) {
    ManijeroTheme(darkTheme = darkTheme) {
        ConnectionScreen(state = state, onInputChange = {}, onCheck = {}, onReset = {}, onBack = {})
    }
}

@Preview(name = "Conexión — sin comprobar")
@Composable
private fun ConnectionIdlePreview() = ConnectionPreview(
    ConnectionState(PREVIEW_DEFAULT_URL, PREVIEW_DEFAULT_URL, ServiceAddressSource.Default),
)

@Preview(name = "Conexión — comprobando")
@Composable
private fun ConnectionCheckingPreview() = ConnectionPreview(
    ConnectionState(PREVIEW_SAVED_URL, PREVIEW_SAVED_URL, ServiceAddressSource.Saved, checking = true),
)

@Preview(name = "Conexión — listo")
@Composable
private fun ConnectionReadyPreview() = ConnectionPreview(
    ConnectionState(PREVIEW_SAVED_URL, PREVIEW_SAVED_URL, ServiceAddressSource.Saved, notice = ConnectionNotice.READY),
)

@Preview(name = "Conexión — todavía no está listo", fontScale = 2f, widthDp = 320)
@Composable
private fun ConnectionNotReadyPreview() = ConnectionPreview(
    ConnectionState(PREVIEW_SAVED_URL, PREVIEW_SAVED_URL, ServiceAddressSource.Saved, notice = ConnectionNotice.NOT_READY),
)

@Preview(name = "Conexión — no se puede conectar, oscuro")
@Composable
private fun ConnectionUnreachablePreview() = ConnectionPreview(
    ConnectionState(PREVIEW_SAVED_URL, PREVIEW_SAVED_URL, ServiceAddressSource.Saved, notice = ConnectionNotice.UNREACHABLE),
    darkTheme = true,
)

@Preview(name = "Conexión — dirección no válida")
@Composable
private fun ConnectionInvalidPreview() = ConnectionPreview(
    ConnectionState("192.168.1.20", PREVIEW_DEFAULT_URL, ServiceAddressSource.Default, notice = ConnectionNotice.INVALID_ADDRESS),
)
