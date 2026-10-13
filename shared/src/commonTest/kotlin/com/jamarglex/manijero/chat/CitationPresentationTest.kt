package com.jamarglex.manijero.chat

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class CitationPresentationTest {
    private fun source(
        title: String = "Solicitud única de la PAC",
        issuingBody: String = "Ministerio de Agricultura, Pesca y Alimentación",
        url: String = "https://www.mapa.gob.es/",
        location: String = "Información de la solicitud única",
        publishedOrUpdatedOn: String = "2026-01-15",
        verifiedOn: String = "2026-10-01",
        excerpt: String = "La solicitud única es el procedimiento anual para solicitar determinadas ayudas de la PAC.",
    ) = AnswerSource(
        title = title,
        issuing_body = issuingBody,
        url = url,
        location = location,
        published_or_updated_on = publishedOrUpdatedOn,
        verified_on = verifiedOn,
        excerpt = excerpt,
    )

    /** Rebuilds the server answer from the rendered segments; replacing references with `[n]`. */
    private fun reconstruct(segments: List<AnswerSegment>): String = segments.joinToString("") { segment ->
        when (segment) {
            is AnswerSegment.Text -> segment.text
            is AnswerSegment.Reference -> "[${segment.number}]"
        }
    }

    private fun presentation(answer: String, sources: List<AnswerSource>) =
        answerSourcePresentation(AnswerStatus.answered, answer, sources)

    // --- conforming mapping and text fidelity ---

    @Test
    fun `a conforming reply maps each marker to its card and keeps the text byte-for-byte`() {
        val answer = "La primera frase. [1] La segunda frase. [2]"
        val result = presentation(answer, listOf(source(), source(title = "Otra fuente")))

        assertEquals(
            listOf(
                AnswerSegment.Text("La primera frase. "),
                AnswerSegment.Reference(1),
                AnswerSegment.Text(" La segunda frase. "),
                AnswerSegment.Reference(2),
            ),
            result.segments,
        )
        assertEquals(listOf(1, 2), result.cards.map { it.number })
        assertEquals(answer, reconstruct(result.segments))
    }

    @Test
    fun `a repeated marker that still matches the cited set is conforming`() {
        val answer = "La misma fuente dos veces. [1] Y otra vez. [1]"
        val result = presentation(answer, listOf(source()))

        assertEquals(
            listOf(
                AnswerSegment.Text("La misma fuente dos veces. "),
                AnswerSegment.Reference(1),
                AnswerSegment.Text(" Y otra vez. "),
                AnswerSegment.Reference(1),
            ),
            result.segments,
        )
        assertEquals(listOf(1), result.cards.map { it.number })
        assertEquals(answer, reconstruct(result.segments))
    }

    @Test
    fun `a reply without sources adds no card and keeps the text unchanged`() {
        val answer = "Una respuesta sin ninguna cita."
        val result = presentation(answer, emptyList())

        assertEquals(listOf(AnswerSegment.Text(answer)), result.segments)
        assertTrue(result.cards.isEmpty())
    }

    // --- non-conforming degradation (fail closed, including carried finding F1) ---

    @Test
    fun `an absent marker set leaves the text unchanged and numbers no card`() {
        val answer = "Una respuesta sin citas."
        val result = presentation(answer, listOf(source()))

        assertEquals(listOf(AnswerSegment.Text(answer)), result.segments)
        assertEquals(listOf<Int?>(null), result.cards.map { it.number })
        assertEquals(answer, reconstruct(result.segments))
    }

    @Test
    fun `the carried non-prefix payload rewrites no marker and numbers no card`() {
        // Reproduces grounded_answer_generation F1: a one-element sources list with a `[2]` marker.
        val answer = "El plazo sintético de prueba. [2]"
        val result = presentation(answer, listOf(source()))

        assertEquals(listOf(AnswerSegment.Text(answer)), result.segments)
        assertEquals(listOf<Int?>(null), result.cards.map { it.number })
        assertEquals(answer, reconstruct(result.segments))
    }

    @Test
    fun `a sparse marker set leaves the text unchanged`() {
        val answer = "Primera. [1] Tercera. [3]"
        val result = presentation(answer, listOf(source(), source(), source()))

        assertEquals(listOf(AnswerSegment.Text(answer)), result.segments)
        assertTrue(result.cards.all { it.number == null })
    }

    @Test
    fun `an out-of-range marker leaves the text unchanged`() {
        val answer = "Una frase. [1] Otra. [3]"
        val result = presentation(answer, listOf(source(), source()))

        assertEquals(listOf(AnswerSegment.Text(answer)), result.segments)
        assertTrue(result.cards.all { it.number == null })
    }

    @Test
    fun `a non-numeric marker leaves the text unchanged`() {
        val answer = "Una frase. [a]"
        val result = presentation(answer, listOf(source()))

        assertEquals(listOf(AnswerSegment.Text(answer)), result.segments)
        assertTrue(result.cards.all { it.number == null })
    }

    @Test
    fun `a zero marker leaves the text unchanged`() {
        val answer = "Una frase. [0]"
        val result = presentation(answer, listOf(source()))

        assertEquals(listOf(AnswerSegment.Text(answer)), result.segments)
        assertTrue(result.cards.all { it.number == null })
    }

    @Test
    fun `a leading-zero marker fails closed so the text stays byte-identical`() {
        val answer = "Una frase. [01]"
        val result = presentation(answer, listOf(source()))

        assertEquals(listOf(AnswerSegment.Text(answer)), result.segments)
        assertTrue(result.cards.all { it.number == null })
        assertEquals(answer, reconstruct(result.segments))
    }

    // --- response-state gate ---

    @Test
    fun `an abstention gate never shows evidence from a malformed payload`() {
        val pinned = "No he encontrado esta información en los documentos oficiales que tengo. " +
            "Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."
        val result = answerSourcePresentation(
            status = AnswerStatus.abstained,
            answer = pinned,
            sources = listOf(source()),
        )

        assertEquals(listOf(AnswerSegment.Text(pinned)), result.segments)
        assertTrue(result.cards.isEmpty())
        assertEquals(pinned, reconstruct(result.segments))
    }

    @Test
    fun `a clarification status also fails closed`() {
        val answer = "Necesito saber a qué terreno te refieres. [1]"
        val result = answerSourcePresentation(
            status = AnswerStatus.needs_land_clarification,
            answer = answer,
            sources = listOf(source()),
        )

        assertEquals(listOf(AnswerSegment.Text(answer)), result.segments)
        assertTrue(result.cards.isEmpty())
    }

    // --- card field mapping ---

    @Test
    fun `cards keep payload order and map every field`() {
        val answer = "Primera. [1] Segunda. [2]"
        val result = presentation(
            answer,
            listOf(
                source(
                    title = "Solicitud única de la PAC",
                    issuingBody = "Ministerio de Agricultura, Pesca y Alimentación",
                    location = "Información de la solicitud única",
                    excerpt = "La solicitud única es el procedimiento anual.",
                ),
                source(
                    title = "SIGPAC",
                    issuingBody = "FEGA",
                    location = "Identificación de parcelas",
                    excerpt = "El SIGPAC identifica las parcelas.",
                ),
            ),
        )

        assertEquals(listOf(1, 2), result.cards.map { it.number })
        assertEquals(listOf("Solicitud única de la PAC", "SIGPAC"), result.cards.map { it.title })
        assertEquals(listOf("Ministerio de Agricultura, Pesca y Alimentación", "FEGA"), result.cards.map { it.issuingBody })
        assertEquals(listOf("Información de la solicitud única", "Identificación de parcelas"), result.cards.map { it.location })
        assertEquals("La solicitud única es el procedimiento anual.", result.cards[0].excerpt)
        assertEquals("El SIGPAC identifica las parcelas.", result.cards[1].excerpt)
        assertEquals("01/10/2026", result.cards[0].verifiedOn)
        assertEquals("https://www.mapa.gob.es/", result.cards[0].link)
    }

    @Test
    fun `a blank verification date omits the date`() {
        val result = presentation("[1]", listOf(source(verifiedOn = "")))
        assertNull(result.cards.single().verifiedOn)

        val whitespace = presentation("[1]", listOf(source(verifiedOn = "   ")))
        assertNull(whitespace.cards.single().verifiedOn)
    }

    @Test
    fun `an unparseable verification date is left unchanged on the card`() {
        val result = presentation("[1]", listOf(source(verifiedOn = "2026-1-5")))

        assertEquals("2026-1-5", result.cards.single().verifiedOn)
    }

    @Test
    fun `an unopenable url leaves the card without a link`() {
        val result = presentation("[1]", listOf(source(url = "http://www.mapa.gob.es/")))

        assertNull(result.cards.single().link)
        assertEquals("Solicitud única de la PAC", result.cards.single().title)
    }

    // --- URL guard ---

    @Test
    fun `an https url with a dotted host is openable unchanged`() {
        assertEquals("https://www.mapa.gob.es/", openableOfficialUrl("https://www.mapa.gob.es/"))
        assertEquals("https://www.mapa.gob.es", openableOfficialUrl("https://www.mapa.gob.es"))
        assertEquals("https://www.mapa.gob.es/x?y=1#z", openableOfficialUrl("https://www.mapa.gob.es/x?y=1#z"))
    }

    @Test
    fun `a url with userinfo or a port keeps the dotted host`() {
        assertEquals(
            "https://user@www.mapa.gob.es:443/x",
            openableOfficialUrl("https://user@www.mapa.gob.es:443/x"),
        )
    }

    @Test
    fun `a non-https or non-openable url is refused`() {
        assertNull(openableOfficialUrl("http://www.mapa.gob.es/"))
        assertNull(openableOfficialUrl("HTTPS://www.mapa.gob.es/"))
        assertNull(openableOfficialUrl("javascript:alert(1)"))
        assertNull(openableOfficialUrl("mailto:alguien@example.com"))
        assertNull(openableOfficialUrl(""))
        assertNull(openableOfficialUrl("   "))
    }

    @Test
    fun `an https url without a dotted host is refused`() {
        assertNull(openableOfficialUrl("https://"))
        assertNull(openableOfficialUrl("https://mapa"))
        assertNull(openableOfficialUrl("https:///ruta"))
        assertNull(openableOfficialUrl("https://:443/"))
    }

    @Test
    fun `an https url with whitespace or a control character is refused`() {
        assertNull(openableOfficialUrl("https://www.mapa.gob.es/ mal"))
        assertNull(openableOfficialUrl("https://www.mapa.gob.es/\n"))
        assertNull(openableOfficialUrl("https://www.mapa.gob.es/x\u0000y"))
    }

    // --- date formatting ---

    @Test
    fun `a strict plausible date is formatted as day month year`() {
        assertEquals("01/10/2026", formatVerificationDate("2026-10-01"))
        assertEquals("15/01/2026", formatVerificationDate("2026-01-15"))
        assertEquals("31/12/2026", formatVerificationDate("2026-12-31"))
    }

    @Test
    fun `any other date shape is returned unchanged`() {
        assertEquals("", formatVerificationDate(""))
        assertEquals("2026-1-5", formatVerificationDate("2026-1-5"))
        assertEquals("01/10/2026", formatVerificationDate("01/10/2026"))
        assertEquals("2026/10/01", formatVerificationDate("2026/10/01"))
        assertEquals("2026-10-0", formatVerificationDate("2026-10-0"))
        assertEquals(" 2026-10-01", formatVerificationDate(" 2026-10-01"))
        assertEquals("2026-aa-01", formatVerificationDate("2026-aa-01"))
        assertEquals("2026-13-01", formatVerificationDate("2026-13-01"))
        assertEquals("2026-10-32", formatVerificationDate("2026-10-32"))
        assertEquals("2026-00-10", formatVerificationDate("2026-00-10"))
        assertEquals("2026-10-00", formatVerificationDate("2026-10-00"))
    }
}
