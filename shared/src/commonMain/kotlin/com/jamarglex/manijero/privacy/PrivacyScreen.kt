package com.jamarglex.manijero.privacy

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.theme.ManijeroTheme
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.design.ManijeroScreen
import com.jamarglex.manijero.design.ManijeroSectionHeader
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.privacy_attribute_municipality
import manijero.shared.generated.resources.privacy_attribute_production_method
import manijero.shared.generated.resources.privacy_attribute_water_regime
import manijero.shared.generated.resources.privacy_back
import manijero.shared.generated.resources.privacy_help_body
import manijero.shared.generated.resources.privacy_help_title
import manijero.shared.generated.resources.privacy_intro
import manijero.shared.generated.resources.privacy_local_body_1
import manijero.shared.generated.resources.privacy_local_body_2
import manijero.shared.generated.resources.privacy_local_body_3
import manijero.shared.generated.resources.privacy_local_title
import manijero.shared.generated.resources.privacy_promise_body_1
import manijero.shared.generated.resources.privacy_promise_body_2
import manijero.shared.generated.resources.privacy_promise_title
import manijero.shared.generated.resources.privacy_sent_body_1
import manijero.shared.generated.resources.privacy_sent_lead
import manijero.shared.generated.resources.privacy_sent_not_sent
import manijero.shared.generated.resources.privacy_sent_title
import manijero.shared.generated.resources.privacy_sent_unknown
import manijero.shared.generated.resources.privacy_title
import manijero.shared.generated.resources.coverage_privacy_link

/**
 * The plain-Spanish data-handling notice: what is saved on this device and what may leave it with a
 * question. It is stateless — no reducer, no callback beyond [onBack] — and every fact is carried by
 * text, never by colour alone. The sendable-attribute bullets are driven by [SHARED_LAND_ATTRIBUTES]
 * through [sharedAttributeLabel], so the list cannot silently under-describe the request payload.
 */
@Composable
fun PrivacyScreen(
    onBack: () -> Unit,
    onCoverageClick: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    ManijeroScreen(modifier) {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    text = stringResource(Res.string.privacy_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.semantics { heading() },
                )
                Text(
                    text = stringResource(Res.string.privacy_intro),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            PrivacySection(title = Res.string.privacy_local_title) {
                PrivacyBody(Res.string.privacy_local_body_1)
                PrivacyBody(Res.string.privacy_local_body_2)
                PrivacyBody(Res.string.privacy_local_body_3)
            }

            PrivacySection(title = Res.string.privacy_sent_title) {
                PrivacyBody(Res.string.privacy_sent_body_1)
                PrivacyBody(Res.string.privacy_sent_lead)
                SHARED_LAND_ATTRIBUTES.forEach { attribute ->
                    PrivacyBullet(sharedAttributeLabel(attribute))
                }
                PrivacyBody(Res.string.privacy_sent_unknown)
                PrivacyBody(Res.string.privacy_sent_not_sent)
            }

            PrivacySection(title = Res.string.privacy_promise_title) {
                PrivacyBody(Res.string.privacy_promise_body_1)
                PrivacyBody(Res.string.privacy_promise_body_2)
            }

            PrivacySection(title = Res.string.privacy_help_title) {
                PrivacyBody(Res.string.privacy_help_body)
                TextButton(onClick = onCoverageClick) {
                    Text(stringResource(Res.string.coverage_privacy_link))
                }
            }

            TextButton(
                onClick = onBack,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(Res.string.privacy_back))
            }
    }
}

/** One titled block of the notice. The heading is a text heading, never a colour-only cue. */
@Composable
private fun PrivacySection(
    title: StringResource,
    content: @Composable () -> Unit,
) {
    ManijeroCard(tone = ManijeroCardTone.Outlined) {
        ManijeroSectionHeader(stringResource(title), heading = true)
        content()
    }
}

@Composable
private fun PrivacyBody(text: StringResource) {
    Text(
        text = stringResource(text),
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

/** One sendable-attribute line. The bullet is a plain text character, not an icon. */
@Composable
private fun PrivacyBullet(text: StringResource) {
    Text(
        text = "• " + stringResource(text),
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

/**
 * The copy for one sendable attribute, mapped with an exhaustive, `else`-free `when`: a new
 * [SharedLandAttribute] breaks compilation instead of silently rendering nothing. It is the single
 * place the enum and the on-screen bullets meet, so the notice always lists exactly the attributes
 * the request can send.
 */
private fun sharedAttributeLabel(attribute: SharedLandAttribute): StringResource = when (attribute) {
    SharedLandAttribute.MUNICIPALITY -> Res.string.privacy_attribute_municipality
    SharedLandAttribute.WATER_REGIME -> Res.string.privacy_attribute_water_regime
    SharedLandAttribute.PRODUCTION_METHOD -> Res.string.privacy_attribute_production_method
}

@Preview(name = "Privacy notice")
@Composable
private fun PrivacyNoticePreview() {
    ManijeroTheme { PrivacyScreen(onBack = {}) }
}

@Preview(name = "Privacy notice dark")
@Composable
private fun PrivacyNoticeDarkPreview() {
    ManijeroTheme(darkTheme = true) { PrivacyScreen(onBack = {}) }
}

@Preview(name = "Privacy notice narrow, large text", widthDp = 320, fontScale = 2f)
@Composable
private fun PrivacyNoticeNarrowLargeTextPreview() {
    ManijeroTheme { PrivacyScreen(onBack = {}) }
}
