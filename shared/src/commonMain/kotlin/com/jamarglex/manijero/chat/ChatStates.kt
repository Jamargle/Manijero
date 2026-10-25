package com.jamarglex.manijero.chat

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.jamarglex.manijero.design.ManijeroCallout
import com.jamarglex.manijero.design.ManijeroCalloutTone
import com.jamarglex.manijero.design.ManijeroIcon
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroSpacing
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.chat_home_failure_service
import manijero.shared.generated.resources.chat_home_failure_unreachable
import manijero.shared.generated.resources.chat_home_retry
import manijero.shared.generated.resources.ic_retry
import org.jetbrains.compose.resources.stringResource

/**
 * One recoverable failure. It is rendered from [ChatHomeState.failure] and never appended to the
 * transcript, so a failed request can never look like an assistant answer. The message says in
 * plain Spanish that there is no answer yet, and the always-visible `Reintentar` button resends the
 * exact original wording.
 *
 * The shared danger callout supplies the warning glyph, the `errorContainer`/`error` pair and the
 * polite live region that covers only the message; the retry stays a sibling, focusable control, so
 * the accepted failure/retry split survives by construction. Danger is carried by the text plus the
 * label, never by colour alone; no raw colour is used here.
 *
 * The reducer retains the sent wording for every failure reachable from a submission, so the
 * `Reintentar` action is always actionable here.
 */
@Composable
internal fun ChatFailureNotice(
    failure: RequestFailure,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val message = when (failure) {
        RequestFailure.COULD_NOT_REACH_SERVICE ->
            stringResource(Res.string.chat_home_failure_unreachable)

        RequestFailure.SERVICE_ERROR ->
            stringResource(Res.string.chat_home_failure_service)
    }
    ManijeroCallout(
        text = message,
        tone = ManijeroCalloutTone.Danger,
        modifier = modifier.fillMaxWidth(),
        action = {
            Button(
                onClick = onRetry,
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error,
                    contentColor = MaterialTheme.colorScheme.onError,
                ),
            ) {
                ManijeroIcon(
                    resource = Res.drawable.ic_retry,
                    contentDescription = null,
                    size = ManijeroIconSize.Inline,
                )
                Spacer(modifier = Modifier.width(ManijeroSpacing.Compact))
                Text(stringResource(Res.string.chat_home_retry))
            }
        },
    )
}
