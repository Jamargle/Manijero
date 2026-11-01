package com.jamarglex.manijero.connection

import java.nio.file.Path
import java.nio.file.Paths

/**
 * The JVM system property that marks a Desktop test build. Only the Gradle development `run` task
 * sets it (see `desktopApp/build.gradle.kts`); packaged apps, `runDistributable`, and `runRelease`
 * never do.
 */
const val DESKTOP_TEST_BUILD_PROPERTY = "manijero.testBuild"

/** True only when the property is exactly `"true"`; anything else keeps today's release wiring. */
fun desktopTestBuildEnabled(
    property: String? = System.getProperty(DESKTOP_TEST_BUILD_PROPERTY),
): Boolean = property == "true"

/**
 * The Desktop test-build file for the remembered answer-service address,
 * `~/.manijero/connection-v1.txt`. The development `run` task and the local smoke test read the
 * same file, so the smoke test checks the address the Desktop app really uses.
 */
fun desktopConnectionStorePath(
    home: String = System.getProperty("user.home"),
): Path = Paths.get(home, ".manijero", "connection-v1.txt")
