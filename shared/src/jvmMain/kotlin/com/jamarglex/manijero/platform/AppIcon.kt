package com.jamarglex.manijero.platform

import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.painter.Painter
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.app_icon
import org.jetbrains.compose.resources.painterResource

/** The Desktop window and dock icon: the same artwork as the Android launcher icon. */
@Composable
fun manijeroAppIcon(): Painter = painterResource(Res.drawable.app_icon)
