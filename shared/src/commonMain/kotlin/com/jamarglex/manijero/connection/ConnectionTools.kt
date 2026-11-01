package com.jamarglex.manijero.connection

/**
 * The test-build connection capability a host injects into `App`. Only Android debug builds and the
 * Desktop development `run` task build one; release and packaged builds inject nothing, so the
 * `Ayuda` card and the `Conexión` route do not exist there.
 */
class ConnectionTools(
    val address: ActiveServiceAddress,
    val checker: ServiceStatusChecker,
)
