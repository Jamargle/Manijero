package com.jamarglex.manijero.coverage

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.*
import manijero.shared.generated.resources.coverage_title
import manijero.shared.generated.resources.coverage_intro
import manijero.shared.generated.resources.coverage_section_topics
import manijero.shared.generated.resources.coverage_topic_application
import manijero.shared.generated.resources.coverage_topic_sigpac
import manijero.shared.generated.resources.coverage_topic_olive_aid
import manijero.shared.generated.resources.coverage_topic_procedure
import manijero.shared.generated.resources.coverage_topic_notifications
import manijero.shared.generated.resources.coverage_section_limits
import manijero.shared.generated.resources.coverage_no_coop
import manijero.shared.generated.resources.coverage_no_personal
import manijero.shared.generated.resources.coverage_no_outside
import manijero.shared.generated.resources.coverage_no_unrelated
import manijero.shared.generated.resources.coverage_section_help
import manijero.shared.generated.resources.coverage_help_body
import manijero.shared.generated.resources.coverage_privacy_link

private val MaxWidth = 720.dp

@Composable
fun CoverageScreen(onBack: () -> Unit, onPrivacyClick: () -> Unit, modifier: Modifier = Modifier) {
    Surface(modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
            Column(Modifier.widthIn(max = MaxWidth).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(Res.string.coverage_title), style = MaterialTheme.typography.headlineMedium, modifier = Modifier.semantics { heading() })
                Text(stringResource(Res.string.coverage_intro), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            CoverageSectionView(Res.string.coverage_section_topics, listOf(Res.string.coverage_topic_application, Res.string.coverage_topic_sigpac, Res.string.coverage_topic_olive_aid, Res.string.coverage_topic_procedure, Res.string.coverage_topic_notifications))
            CoverageSectionView(Res.string.coverage_section_limits, listOf(Res.string.coverage_no_coop, Res.string.coverage_no_personal, Res.string.coverage_no_outside, Res.string.coverage_no_unrelated, Res.string.coverage_not_yet_topics))
            CoverageSectionView(Res.string.coverage_section_help, listOf(Res.string.coverage_help_body))
            TextButton(onClick = onPrivacyClick, modifier = Modifier.widthIn(max = MaxWidth).fillMaxWidth()) { Text(stringResource(Res.string.coverage_privacy_link)) }
            TextButton(onClick = onBack, modifier = Modifier.widthIn(max = MaxWidth).fillMaxWidth()) { Text(stringResource(Res.string.privacy_back)) }
        }
    }
}

@Composable private fun CoverageSectionView(title: StringResource, body: List<StringResource>) {
    Column(Modifier.widthIn(max = MaxWidth).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(title), style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
        body.forEach { Text(stringResource(it), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Preview(name = "Coverage") @Composable private fun CoveragePreview() { ManijeroTheme { CoverageScreen({}, {}) } }
@Preview(name = "Coverage narrow, large text", widthDp = 320, fontScale = 2f) @Composable private fun CoverageLargePreview() { ManijeroTheme { CoverageScreen({}, {}) } }
