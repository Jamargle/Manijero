package com.jamarglex.manijero.connection

import kotlin.test.Test
import kotlin.test.assertEquals

/** The address rules a tester's typed text must pass before anything is saved or requested. */
class ServiceAddressTest {
    private fun valid(url: String) = ServiceAddressInput.Valid(url)

    @Test
    fun `surrounding spaces and trailing slashes are removed`() {
        assertEquals(valid("http://192.168.1.20:8000"), normalizeServiceAddress("  http://192.168.1.20:8000/  "))
        assertEquals(valid("http://192.168.1.20:8000"), normalizeServiceAddress("\thttp://192.168.1.20:8000///\n"))
    }

    @Test
    fun `scheme and host are lowercased and a path prefix keeps its case`() {
        assertEquals(
            valid("https://qa.example.org/Manijero/api"),
            normalizeServiceAddress("HTTPS://QA.Example.org/Manijero/api/"),
        )
    }

    @Test
    fun `common local addresses are accepted`() {
        listOf(
            "http://10.0.2.2:8000",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "https://qa.example.org",
            "http://[::1]:8000",
            "http://my-mac.local:1",
            "http://host:65535",
        ).forEach { address -> assertEquals(valid(address), normalizeServiceAddress(address), address) }
    }

    @Test
    fun `the 512 character limit applies after trimming`() {
        val prefix = "http://h/"
        val atLimit = prefix + "a".repeat(MAX_SERVICE_ADDRESS_LENGTH - prefix.length)
        assertEquals(valid(atLimit), normalizeServiceAddress("  $atLimit/  "))
        assertEquals(ServiceAddressInput.Invalid, normalizeServiceAddress(atLimit + "a"))
    }

    @Test
    fun `every refused form is invalid`() {
        listOf(
            "",
            "   ",
            "/",
            "192.168.1.20:8000",
            "ftp://192.168.1.20:8000",
            "file:///etc/hosts",
            "javascript://x",
            "http://",
            "http://:8000",
            "http://host:0",
            "http://host:65536",
            "http://host:99999999999",
            "http://host:",
            "http://host:80a",
            "http://host:-1",
            "http://user:pass@host:8000",
            "http://@host",
            "http://host:8000?x=1",
            "http://host:8000/?x",
            "http://host:8000#frag",
            "http://host name:8000",
            "http://host:8000/a b",
            "http://[::1",
            "http://[]:8000",
            "http://[::1]x",
            "http://a:b:c",
            "http://.host",
            "http:\\\\host",
        ).forEach { input ->
            assertEquals(ServiceAddressInput.Invalid, normalizeServiceAddress(input), "\"$input\" must be refused")
        }
    }

    @Test
    fun `unicode, emoji and control characters are refused without crashing`() {
        listOf(
            "http://olivar.es:8000/ñ",
            "http://🫒.example:8000",
            "http://exa\u0000mple:8000",
            "http://e​xample:8000",
            "http://ｅxample.org",
            "\uD83E",
        ).forEach { input ->
            assertEquals(ServiceAddressInput.Invalid, normalizeServiceAddress(input), "\"$input\" must be refused")
        }
    }
}
