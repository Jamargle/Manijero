package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.jamarglex.manijero.theme.ManijeroLayout
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme

/**
 * The window width from which the shared layout switches to wide padding and wide navigation
 * actions. One value keeps [ManijeroScreen] and [ManijeroTopAppBar] on the same breakpoint.
 */
internal val WideWindowBreakpoint = 840.dp

/**
 * The shared page layout: the `background` role, one vertical scroll, the screen padding from
 * [screenHorizontalPadding], and a centred content column capped at
 * [ManijeroLayout.ContentMaxWidth].
 *
 * It owns no window insets and no top or bottom bar: the shell's `Scaffold` is the single inset
 * owner. The content is a plain [ColumnScope] so a screen can stack its own sections, and the
 * column adds [ManijeroSpacing.Comfortable] between them by default.
 *
 * [bottomBar], when given, stays attached to the bottom of the screen below the scrolling content
 * (the chat composer). It shares the same centred column and horizontal padding, is separated by a
 * 1 dp `outlineVariant` divider, and is capped at [BottomBarMaxHeightFraction] of the screen with
 * its own scroll so enlarged text can never push the content out of view.
 */
@Composable
internal fun ManijeroScreen(
    modifier: Modifier = Modifier,
    bottomBar: (@Composable ColumnScope.() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
        contentColor = MaterialTheme.colorScheme.onBackground,
    ) {
        BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
            val horizontalPadding = screenHorizontalPadding(maxWidth)
            val screenHeight = maxHeight
            Column(modifier = Modifier.fillMaxSize()) {
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .verticalScroll(rememberScrollState())
                        .padding(
                            horizontal = horizontalPadding,
                            vertical = ManijeroLayout.ScreenPaddingVertical,
                        ),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Column(
                        modifier = Modifier
                            .widthIn(max = ManijeroLayout.ContentMaxWidth)
                            .fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Comfortable),
                        content = content,
                    )
                }
                if (bottomBar != null) {
                    HorizontalDivider(
                        thickness = ManijeroLayout.BorderWidth,
                        color = MaterialTheme.colorScheme.outlineVariant,
                    )
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = screenHeight * BottomBarMaxHeightFraction)
                            .verticalScroll(rememberScrollState())
                            .padding(
                                horizontal = horizontalPadding,
                                vertical = ManijeroSpacing.Small,
                            ),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Column(
                            modifier = Modifier
                                .widthIn(max = ManijeroLayout.ContentMaxWidth)
                                .fillMaxWidth(),
                            verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Compact),
                            content = bottomBar,
                        )
                    }
                }
            }
        }
    }
}

/** The largest share of the screen height a pinned [ManijeroScreen] bottom bar may take. */
internal const val BottomBarMaxHeightFraction = 0.5f

/**
 * Pure padding decision for [ManijeroScreen]: compact windows keep the 24 dp screen padding and
 * windows at or above [WideWindowBreakpoint] get 40 dp. Kept as a function so the boundary is
 * unit-tested without a renderer.
 */
internal fun screenHorizontalPadding(windowWidth: Dp): Dp =
    if (windowWidth >= WideWindowBreakpoint) {
        ManijeroLayout.ScreenPaddingHorizontalWide
    } else {
        ManijeroLayout.ScreenPaddingHorizontal
    }

@Composable
private fun ManijeroScreenPreviewContent() {
    Text(text = "Título de la pantalla", style = MaterialTheme.typography.headlineMedium)
    Text(
        text = "Contenido de ejemplo sobre el fondo compartido, con una columna centrada.",
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    ManijeroCard { Text(text = "Una tarjeta dentro de la pantalla.") }
}

@Preview(name = "ManijeroScreen — claro", widthDp = 400, heightDp = 480)
@Composable
private fun ManijeroScreenLightPreview() {
    ManijeroTheme(darkTheme = false) { ManijeroScreen { ManijeroScreenPreviewContent() } }
}

@Preview(name = "ManijeroScreen — oscuro", widthDp = 400, heightDp = 480)
@Composable
private fun ManijeroScreenDarkPreview() {
    ManijeroTheme(darkTheme = true) { ManijeroScreen { ManijeroScreenPreviewContent() } }
}

@Preview(name = "ManijeroScreen — texto grande", widthDp = 360, heightDp = 640, fontScale = 2f)
@Composable
private fun ManijeroScreenLargeTextPreview() {
    ManijeroTheme(darkTheme = false) { ManijeroScreen { ManijeroScreenPreviewContent() } }
}
