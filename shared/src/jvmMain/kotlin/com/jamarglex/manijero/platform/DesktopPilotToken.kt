package com.jamarglex.manijero.platform

import com.jamarglex.manijero.chat.PilotToken
import java.io.IOException

/**
 * Classpath resource the Desktop build writes from the git-ignored `pilot-token.local`
 * (`desktopApp` task `generatePilotTokenResource`). It is absent when no token was saved.
 */
const val DESKTOP_PILOT_TOKEN_RESOURCE = "manijero/pilot-token.txt"

/**
 * The pilot token built into this Desktop app, or `null` when the build has none or the resource
 * is not a pilot token. Nothing about the resource or its content is logged.
 */
fun desktopPilotToken(
    readResource: (String) -> String? = ::readClasspathResource,
): PilotToken? = PilotToken.fromBuildSetting(readResource(DESKTOP_PILOT_TOKEN_RESOURCE)?.trim())

private fun readClasspathResource(name: String): String? = try {
    PilotToken::class.java.classLoader?.getResourceAsStream(name)?.use { it.readBytes().decodeToString() }
} catch (_: IOException) {
    null
}
