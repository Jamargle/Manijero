package com.jamarglex.manijero

import android.content.Context
import io.ktor.client.HttpClient

/**
 * Release builds never have test tools: no `Conexión` screen, no saved address, and the fixed
 * answer URL. The return type is `Nothing?` so this file needs nothing from the connection package;
 * `TestBuildGatingGuardTest` keeps it that way.
 */
@Suppress("UNUSED_PARAMETER", "FunctionOnlyReturningConstant")
fun testBuildConnectionTools(
    context: Context,
    defaultUrl: String,
    client: HttpClient,
): Nothing? = null
