package com.jamarglex.manijero.platform

import java.io.IOException

/**
 * Classpath resource the Desktop build writes from the `manijeroEnvironment` setting
 * (`desktopApp` task `generateEnvironmentResource`). It holds no token: the environment name and, in
 * QA, the answer-service address. A missing resource means a local run (unit tests, IDE runs).
 */
const val DESKTOP_ENVIRONMENT_RESOURCE = "manijero/environment.properties"

private const val MAX_ADDRESS_LENGTH = 512
private val QA_ADDRESS = Regex(
    "^https://[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*" +
        "(:([0-9]{1,5}))?(/[A-Za-z0-9._~%!$&'()*+,;=:@/-]*)?$",
)

/** Which environment this Desktop app was built for, and what that changes at runtime. */
sealed interface DesktopEnvironment {
    /** The window title. */
    val title: String

    /** The folder under the home directory that holds lands, the welcome flag, and the saved address. */
    val dataFolder: String

    /** The answer-service address used until a test build saves another one. */
    fun defaultAskBaseUrl(): String

    data object Local : DesktopEnvironment {
        override val title: String = "Manijero"
        override val dataFolder: String = ".manijero"

        override fun defaultAskBaseUrl(): String = desktopAskBaseUrl()
    }

    /** QA ignores the runtime address overrides, so this app never targets a local address by default. */
    data class Qa(val askBaseUrl: String) : DesktopEnvironment {
        override val title: String = "Manijero QA"
        override val dataFolder: String = ".manijero-qa"

        override fun defaultAskBaseUrl(): String = askBaseUrl
    }
}

/** Thrown when the built-in environment resource is present but unusable; the message is plain. */
class DesktopEnvironmentException(message: String) : IllegalStateException(message)

/**
 * The environment built into this Desktop app. A missing resource is local; a present but malformed
 * one stops startup instead of silently running as local. Nothing about the content is echoed.
 */
fun desktopEnvironment(
    readResource: (String) -> String? = ::readEnvironmentResource,
): DesktopEnvironment {
    val text = readResource(DESKTOP_ENVIRONMENT_RESOURCE) ?: return DesktopEnvironment.Local
    val entries = mutableMapOf<String, String>()
    for (line in text.lineSequence().map { it.trim() }.filter { it.isNotEmpty() }) {
        val separator = line.indexOf('=')
        if (separator <= 0) throw malformed()
        val key = line.substring(0, separator)
        if (key in entries) throw malformed()
        entries[key] = line.substring(separator + 1)
    }
    if (!entries.keys.all { it == "environment" || it == "askBaseUrl" }) throw malformed()
    return when (entries["environment"]) {
        "local" -> {
            if ("askBaseUrl" in entries) throw malformed()
            DesktopEnvironment.Local
        }
        "qa" -> DesktopEnvironment.Qa(validQaAddress(entries["askBaseUrl"]) ?: throw malformed())
        else -> throw malformed()
    }
}

/** The address without surrounding whitespace or trailing `/`, or `null` when it is not a valid QA address. */
fun validQaAddress(raw: String?): String? {
    val address = raw?.trim()?.trimEnd('/') ?: return null
    if (address.isEmpty() || address.length > MAX_ADDRESS_LENGTH) return null
    val match = QA_ADDRESS.matchEntire(address) ?: return null
    val port = match.groups[5]?.value?.toInt()
    if (port != null && port !in 1..65535) return null
    return address
}

private fun malformed() = DesktopEnvironmentException(
    "This Manijero app was built with an unusable environment setting. Build it again with ./scripts/init.sh --desktop-qa.",
)

private fun readEnvironmentResource(name: String): String? = try {
    DesktopEnvironment::class.java.classLoader?.getResourceAsStream(name)?.use { it.readBytes().decodeToString() }
} catch (_: IOException) {
    null
}
