package com.jamarglex.manijero

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import org.jetbrains.compose.resources.stringResource
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.chat_home_ask
import manijero.shared.generated.resources.chat_home_description
import manijero.shared.generated.resources.chat_home_question_hint
import manijero.shared.generated.resources.chat_home_lands
import manijero.shared.generated.resources.chat_home_question_label
import manijero.shared.generated.resources.chat_home_submitted
import manijero.shared.generated.resources.chat_home_title

@Composable
fun App() {
    var state by remember { mutableStateOf(ChatHomeState()) }

    ChatHomeScreen(
        state = state,
        onAction = { action -> state = state.reduce(action) },
        onLandsClick = {},
    )
}

@Composable
internal fun ChatHomeScreen(
    state: ChatHomeState,
    onAction: (ChatHomeAction) -> Unit,
    onLandsClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 32.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 720.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    text = stringResource(Res.string.chat_home_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onBackground,
                )
                Text(
                    text = stringResource(Res.string.chat_home_description),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            OutlinedTextField(
                value = state.question,
                onValueChange = { onAction(ChatHomeAction.QuestionChanged(it)) },
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 720.dp),
                label = { Text(stringResource(Res.string.chat_home_question_label)) },
                placeholder = { Text(stringResource(Res.string.chat_home_question_hint)) },
                minLines = 3,
                maxLines = 6,
            )

            Row(
                modifier = Modifier.fillMaxWidth().widthIn(max = 720.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(
                    onClick = { onAction(ChatHomeAction.AskClicked) },
                    enabled = state.canAsk,
                ) {
                    Text(stringResource(Res.string.chat_home_ask))
                }
                TextButton(onClick = onLandsClick) {
                    Text(stringResource(Res.string.chat_home_lands))
                }
            }

            if (state.submittedQuestion != null) {
                Text(
                    text = stringResource(Res.string.chat_home_submitted),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Preview(name = "Chat home")
@Composable
private fun ChatHomePreview() {
    MaterialTheme { ChatHomeScreen(ChatHomeState(), {}, {}) }
}

@Preview(name = "Chat home with question")
@Composable
private fun ChatHomeWithQuestionPreview() {
    MaterialTheme {
        ChatHomeScreen(
            state = ChatHomeState(question = "¿Cuándo debo revisar mi olivar?", submittedQuestion = "¿Cuándo debo revisar mi olivar?"),
            onAction = {},
            onLandsClick = {},
        )
    }
}
