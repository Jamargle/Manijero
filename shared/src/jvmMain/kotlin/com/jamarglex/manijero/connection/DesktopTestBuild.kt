package com.jamarglex.manijero.connection

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
