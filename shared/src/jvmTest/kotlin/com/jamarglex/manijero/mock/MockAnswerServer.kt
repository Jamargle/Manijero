package com.jamarglex.manijero.mock

import com.jamarglex.manijero.chat.AskResponse
import com.jamarglex.manijero.chat.answerJson
import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.server.application.Application
import io.ktor.server.application.ApplicationCall
import io.ktor.server.cio.CIO
import io.ktor.server.engine.embeddedServer
import io.ktor.server.request.httpMethod
import io.ktor.server.request.path
import io.ktor.server.request.receiveText
import io.ktor.server.response.respondText
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import io.ktor.server.routing.route
import io.ktor.server.routing.routing
import java.io.File
import kotlin.system.exitProcess

/**
 * Test-only stand-in for the local answer service, started by `./scripts/init.sh --mock`.
 *
 * It serves only the committed contract examples (see [selectExample]), binds to the address it is
 * given (the start command always passes `127.0.0.1`), and logs one line per request holding only
 * the method, a known path, the status code, and the served example's file name. Question text,
 * land data, and headers are never read into a log line.
 */
const val MOCK_SERVICE_NAME = "manijero-mock"

const val HEALTH_BODY = """{"status":"ok","service":"$MOCK_SERVICE_NAME"}"""
const val READY_BODY = """{"status":"ready","service":"$MOCK_SERVICE_NAME"}"""
const val MALFORMED_BODY = """{"detail":"Malformed request."}"""
const val CONTRACT_VIOLATION_BODY = """{"detail":"Request does not match the contract."}"""
const val NOT_FOUND_BODY = """{"detail":"Not found."}"""

/** The line prefix the start command looks for when the service refuses to start. */
const val CANNOT_START_PREFIX = "Mock answer service cannot start:"

private val knownPaths = setOf("/health", "/ready", "/ask")
private const val NO_EXAMPLE = "-"

fun Application.mockAnswerModule(examples: ContractExamples, log: (String) -> Unit) {
    routing {
        get("/health") {
            call.respondJson(HttpStatusCode.OK, HEALTH_BODY, NO_EXAMPLE, log)
        }
        get("/ready") {
            call.respondJson(HttpStatusCode.OK, READY_BODY, NO_EXAMPLE, log)
        }
        post("/ask") {
            val body = try {
                call.receiveText()
            } catch (_: Exception) {
                null
            }
            when (val validation = body?.let(::validateAskBody) ?: AskValidation.Malformed) {
                AskValidation.Malformed ->
                    call.respondJson(HttpStatusCode.BadRequest, MALFORMED_BODY, NO_EXAMPLE, log)
                AskValidation.ContractViolation ->
                    call.respondJson(HttpStatusCode.UnprocessableEntity, CONTRACT_VIOLATION_BODY, NO_EXAMPLE, log)
                is AskValidation.Valid -> {
                    val served = selectExample(validation.request, examples)
                    val text = answerJson.encodeToString(AskResponse.serializer(), served.response)
                    call.respondJson(HttpStatusCode.OK, text, served.fileName, log)
                }
            }
        }
        // Everything else, including a wrong method on a known path, is a generic 404.
        route("{...}") {
            handle {
                call.respondJson(HttpStatusCode.NotFound, NOT_FOUND_BODY, NO_EXAMPLE, log)
            }
        }
    }
}

private suspend fun ApplicationCall.respondJson(
    status: HttpStatusCode,
    body: String,
    exampleFileName: String,
    log: (String) -> Unit,
) {
    // Only a fixed known path is logged; any other path could carry user-typed text.
    val path = request.path().takeIf { it in knownPaths } ?: "(other path)"
    log("mock-answer-server ${request.httpMethod.value} $path ${status.value} $exampleFileName")
    respondText(body, ContentType.Application.Json, status)
}

/** Command-line options passed by `./scripts/init.sh --mock`. */
data class MockServerOptions(val examplesDirectory: File, val host: String, val port: Int)

/** Parses `--examples <dir> --host <host> --port <port>`; returns null when anything is wrong. */
fun parseMockServerOptions(args: Array<String>): MockServerOptions? {
    if (args.size % 2 != 0) return null
    val values = args.toList().chunked(2).associate { (key, value) -> key to value }
    if (values.keys != setOf("--examples", "--host", "--port")) return null
    val port = values.getValue("--port").toIntOrNull()?.takeIf { it in 1..65_535 } ?: return null
    return MockServerOptions(File(values.getValue("--examples")), values.getValue("--host"), port)
}

fun main(args: Array<String>) {
    val options = parseMockServerOptions(args) ?: run {
        System.err.println("$CANNOT_START_PREFIX expected --examples <folder> --host <address> --port <number>.")
        exitProcess(2)
    }
    val examples = try {
        loadContractExamples(options.examplesDirectory)
    } catch (failure: ContractExampleException) {
        System.err.println("$CANNOT_START_PREFIX ${failure.message}")
        exitProcess(1)
    }
    val server = embeddedServer(CIO, port = options.port, host = options.host) {
        mockAnswerModule(examples) { line -> println(line) }
    }
    try {
        server.start(wait = false)
    } catch (_: Exception) {
        System.err.println("$CANNOT_START_PREFIX port ${options.port} on ${options.host} could not be opened.")
        exitProcess(1)
    }
    println("Mock answer service listening on http://${options.host}:${options.port}")
    Thread.currentThread().join()
}
