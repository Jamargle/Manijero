package com.jamarglex.manijero.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import com.jamarglex.manijero.AnswerFeedback
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroSpacing
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.chat_feedback_failed
import manijero.shared.generated.resources.chat_feedback_not_useful
import manijero.shared.generated.resources.chat_feedback_not_useful_description
import manijero.shared.generated.resources.chat_feedback_thanks
import manijero.shared.generated.resources.chat_feedback_useful
import manijero.shared.generated.resources.chat_feedback_useful_description
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource

/**
 * The quiet rating row of one finished answer: `Útil` and `No útil` as two neutral outlined buttons,
 * or the single confirmation line once the service accepted the rating.
 *
 * It is a sibling of the answer card, never inside its merged live region, and it is deliberately
 * calmer than `Preguntar`: never filled, no icon, badge, checkmark or success colour. Every visible
 * state is readable from text or semantics: the buttons carry their own accessible names and a 48 dp
 * target, both are disabled while the send is in flight (so one answer cannot be counted twice), a
 * failure keeps both enabled and adds the plain retry line beneath, and a success leaves nothing to
 * tap. Wrapping, not clipping, is how the row survives large text.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun AnswerFeedbackControl(
    feedback: AnswerFeedback,
    onRating: (AnswerRating) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Micro),
    ) {
        if (feedback is AnswerFeedback.Sent) {
            Text(
                text = stringResource(Res.string.chat_feedback_thanks),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.testTag(ChatTestTags.FEEDBACK_SENT),
            )
        } else {
            val enabled = feedback !is AnswerFeedback.Sending
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
                verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small),
            ) {
                FeedbackButton(
                    label = Res.string.chat_feedback_useful,
                    description = Res.string.chat_feedback_useful_description,
                    enabled = enabled,
                    onClick = { onRating(AnswerRating.USEFUL) },
                    modifier = Modifier.testTag(ChatTestTags.FEEDBACK_USEFUL),
                )
                FeedbackButton(
                    label = Res.string.chat_feedback_not_useful,
                    description = Res.string.chat_feedback_not_useful_description,
                    enabled = enabled,
                    onClick = { onRating(AnswerRating.NOT_USEFUL) },
                    modifier = Modifier.testTag(ChatTestTags.FEEDBACK_NOT_USEFUL),
                )
            }
            if (feedback is AnswerFeedback.Failed) {
                Text(
                    text = stringResource(Res.string.chat_feedback_failed),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/**
 * One rating button: an outlined, never filled control with its own focusable node, its own
 * accessible name and the accepted minimum touch target. The visible label stays short so the row
 * wraps at large text instead of teaching an icon.
 */
@Composable
private fun FeedbackButton(
    label: StringResource,
    description: StringResource,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val accessibleName = stringResource(description)
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier
            .heightIn(min = ManijeroLayout.MinTouchTarget)
            .semantics { contentDescription = accessibleName },
    ) {
        Text(text = stringResource(label))
    }
}
