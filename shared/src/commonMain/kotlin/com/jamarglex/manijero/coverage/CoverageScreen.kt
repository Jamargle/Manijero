package com.jamarglex.manijero.coverage

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.design.ManijeroCallout
import com.jamarglex.manijero.design.ManijeroCalloutTone
import com.jamarglex.manijero.design.ManijeroCard
import com.jamarglex.manijero.design.ManijeroCardTone
import com.jamarglex.manijero.design.ManijeroScreen
import com.jamarglex.manijero.design.ManijeroSectionHeader
import com.jamarglex.manijero.theme.ManijeroTheme
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.*

@Composable
fun CoverageScreen(onPrivacyClick: () -> Unit, modifier: Modifier = Modifier) {
    ManijeroScreen(modifier) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(Res.string.coverage_title), style = MaterialTheme.typography.headlineMedium, modifier = Modifier.semantics { heading() })
            Text(stringResource(Res.string.coverage_intro), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        ManijeroCard(tone = ManijeroCardTone.Outlined) {
            ManijeroSectionHeader(stringResource(Res.string.coverage_section_topics), heading = true)
            CoverageLines(listOf(Res.string.coverage_topic_application, Res.string.coverage_topic_sigpac, Res.string.coverage_topic_olive_aid, Res.string.coverage_topic_procedure, Res.string.coverage_topic_notifications))
        }
        ManijeroCallout(
            title = stringResource(Res.string.coverage_section_limits),
            text = coverageLimitsText(),
            tone = ManijeroCalloutTone.Info,
        )
        ManijeroCard(tone = ManijeroCardTone.Outlined) {
            ManijeroSectionHeader(stringResource(Res.string.coverage_section_help), heading = true)
            CoverageLines(listOf(Res.string.coverage_help_body))
            TextButton(onClick = onPrivacyClick, modifier = Modifier.fillMaxWidth()) { Text(stringResource(Res.string.coverage_privacy_link)) }
        }
    }
}

@Composable
private fun coverageLimitsText(): String {
    val resources = listOf(
        Res.string.coverage_no_coop,
        Res.string.coverage_no_personal,
        Res.string.coverage_no_outside,
        Res.string.coverage_no_unrelated,
        Res.string.coverage_not_yet_topics,
    )
    val lines = resources.map { "• ${stringResource(it)}" }
    return lines.joinToString("\n\n")
}

@Composable
private fun CoverageLines(lines: List<StringResource>) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        lines.forEach { Text("• " + stringResource(it), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Preview(name = "Coverage") @Composable private fun CoveragePreview() { ManijeroTheme { CoverageScreen({}) } }
@Preview(name = "Coverage dark") @Composable private fun CoverageDarkPreview() { ManijeroTheme(darkTheme = true) { CoverageScreen({}) } }
@Preview(name = "Coverage narrow, large text", widthDp = 320, fontScale = 2f) @Composable private fun CoverageLargePreview() { ManijeroTheme { CoverageScreen({}) } }
