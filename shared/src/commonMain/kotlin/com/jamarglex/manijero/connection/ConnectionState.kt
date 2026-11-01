package com.jamarglex.manijero.connection

/** The one message the `Conexión` screen shows after an action, so copy and tests can tell them apart. */
enum class ConnectionNotice {
    READY,
    NOT_READY,
    READY_UNKNOWN,
    UNREACHABLE,
    NOT_MANIJERO,
    INVALID_ADDRESS,
    STORAGE_FAILED,
    RESET_TO_DEFAULT,
}

/**
 * Pure state for the `Conexión` screen. [input] is the text in the field; [activeUrl] and
 * [activeSource] describe the address questions use right now. [checking] is true while a check is
 * in flight, so `Comprobar` and the reset are disabled. No Compose or platform type belongs here.
 */
data class ConnectionState(
    val input: String,
    val activeUrl: String,
    val activeSource: ServiceAddressSource,
    val checking: Boolean = false,
    val notice: ConnectionNotice? = null,
)

sealed interface ConnectionAction {
    /** The screen was opened: the field shows the address in use and no old message remains. */
    data class Opened(val activeUrl: String, val activeSource: ServiceAddressSource) : ConnectionAction

    /** The person typed; the typed text is kept even after an error. */
    data class InputChanged(val text: String) : ConnectionAction

    /** The address was refused before any request or save, or the device store refused it. */
    data class Refused(val notice: ConnectionNotice) : ConnectionAction

    /** [url] was saved and is now in use; the check is running. */
    data class CheckStarted(val url: String) : ConnectionAction

    data class CheckFinished(val result: ServiceCheckResult) : ConnectionAction

    /** The check stopped because the person left the screen; no message is shown. */
    data object CheckCancelled : ConnectionAction

    /** The saved address was deleted and [defaultUrl] is in use again. */
    data class ResetDone(val defaultUrl: String) : ConnectionAction
}

fun ConnectionState.reduce(action: ConnectionAction): ConnectionState = when (action) {
    is ConnectionAction.Opened -> ConnectionState(
        input = action.activeUrl,
        activeUrl = action.activeUrl,
        activeSource = action.activeSource,
    )
    is ConnectionAction.InputChanged -> copy(input = action.text)
    is ConnectionAction.Refused -> copy(checking = false, notice = action.notice)
    is ConnectionAction.CheckStarted -> copy(
        input = action.url,
        activeUrl = action.url,
        activeSource = ServiceAddressSource.Saved,
        checking = true,
        notice = null,
    )
    is ConnectionAction.CheckFinished -> copy(checking = false, notice = action.result.toNotice())
    ConnectionAction.CheckCancelled -> copy(checking = false, notice = null)
    is ConnectionAction.ResetDone -> copy(
        input = action.defaultUrl,
        activeUrl = action.defaultUrl,
        activeSource = ServiceAddressSource.Default,
        checking = false,
        notice = ConnectionNotice.RESET_TO_DEFAULT,
    )
}

fun ServiceCheckResult.toNotice(): ConnectionNotice = when (this) {
    ServiceCheckResult.Ready -> ConnectionNotice.READY
    ServiceCheckResult.NotReady -> ConnectionNotice.NOT_READY
    ServiceCheckResult.ReadyUnknown -> ConnectionNotice.READY_UNKNOWN
    ServiceCheckResult.Unreachable -> ConnectionNotice.UNREACHABLE
    ServiceCheckResult.NotManijero -> ConnectionNotice.NOT_MANIJERO
}
