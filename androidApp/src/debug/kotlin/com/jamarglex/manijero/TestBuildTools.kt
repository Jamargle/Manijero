package com.jamarglex.manijero

import android.content.Context
import com.jamarglex.manijero.connection.ActiveServiceAddress
import com.jamarglex.manijero.connection.AndroidServiceAddressStore
import com.jamarglex.manijero.connection.ConnectionTools
import com.jamarglex.manijero.connection.KtorServiceStatusChecker
import io.ktor.client.HttpClient

/**
 * Debug builds only: the `Conexión` test tools. The address is remembered in this app's private
 * preferences and the check reuses the answer client. The release source set has its own
 * `testBuildConnectionTools` that returns `null`.
 */
fun testBuildConnectionTools(
    context: Context,
    defaultUrl: String,
    client: HttpClient,
): ConnectionTools? = ConnectionTools(
    address = ActiveServiceAddress(defaultUrl, AndroidServiceAddressStore(context)),
    checker = KtorServiceStatusChecker(client),
)
