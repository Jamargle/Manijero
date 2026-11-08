# Guion de la demostración de Manijero

Este guion sirve para enseñar Manijero en directo sin improvisar ni prometer de más. Se apoya en
el corpus aprobado de la Solicitud Única andaluza de 2026 y en un paquete de revisión **sintético**.
No es una revisión legal, no mide la calidad general de las respuestas y no incluye terrenos.

Los pasos marcados **(manual)** se hacen en la pantalla, delante del público. Todo lo demás es lo
que el comando ya ha comprobado.

## Antes de empezar

1. Abre **Ollama** (el icono de la llama en la barra de menús) y espera diez segundos.
2. En una Terminal, en la carpeta de Manijero, arranca el servicio:

   ```sh
   ./scripts/init.sh --local-rag-start
   ```

   Espera `Result: the local answer service started at http://127.0.0.1:8000.`
3. Haz el ensayo automático:

   ```sh
   ./scripts/init.sh --demo-rehearsal
   ```

   Espera cuatro líneas `PASS` y
   `Result: the demo rehearsal passed (4 of 4 steps) ...`. Ese `Result:` también dice que la
   actualización revisada usó datos sintéticos y que el conocimiento aprobado no cambió.
4. Si alguna línea no es `PASS`, no empieces la demostración: sigue el apartado
   [Si algo no sale](#si-algo-no-sale).

## Qué es real y qué es de ensayo

- **Real:** el catálogo y los pasajes aprobados de la PAC 2026 (tres temas: canal de presentación,
  fecha de presentación y fecha de modificación).
- **De ensayo:** la actualización revisada usa un Real Decreto 2200/2099 inventado, con la
  revisora ficticia `Revisora de ensayo`. Se ejecuta sobre una copia temporal y **nunca** cambia
  `knowledge/`.
- La demostración no calcula ayudas, no comprueba si alguien cumple los requisitos y no da
  conclusiones legales.

## Orden de la demostración

1. **(manual)** Abre la app de prueba local con `./scripts/init.sh --desktop` o
   `./scripts/init.sh --android-run`. Habla solo de la app de prueba; la app de QA y la de release
   no forman parte de esta demostración.
2. **(manual)** Pregunta: **«¿Cuál es la fecha final para presentar la solicitud única de 2026?»**
   Debe aparecer una respuesta con tarjetas de fuente y, debajo, la frase fija
   `No tiene en cuenta tus terrenos.`
   Di: «responde solo con lo que hay en las fuentes aprobadas y enseña de dónde lo saca».
3. **(manual)** Pregunta trampa: **«¿Qué importe de ayuda me corresponde por hectárea?»**
   Debe aparecer `Sin respuesta segura`. Di: «cuando no hay base suficiente, no inventa: prefiere
   no responder». Este caso no es un fallo de la app.
4. **(manual)** Pulsa `Inspeccionar` en la respuesta anterior. Se abre
   `Inspección de la respuesta`, con `Búsqueda`, `Pasajes encontrados` y `Comprobación`.
   - Solo existe en una compilación de prueba local, con el servicio en `127.0.0.1` y el perfil
     `development`.
   - Si no aparece `Inspeccionar`: no lo busques ni lo prometas. Di «la traza de depuración solo
     está en la compilación de prueba local» y pasa al paso 5.
5. **(manual, explicación)** Explica la actualización revisada, que el comando ya probó:
   - primero se prepara un borrador y un intento de mezcla sin aprobación queda **rechazado**;
   - una persona con nombre —aquí `Revisora de ensayo`— aprueba;
   - solo entonces se escribe, y solo en la copia temporal.
   Puedes enseñar el código del paso sin ejecutarlo otra vez. No digas que se ha revisado
   conocimiento real.
6. **(manual)** Cierra con los límites del apartado siguiente, sin añadir promesas.

## Lo que no debes prometer

- No hay **aclaración de terrenos** en esta demostración: el corpus aprobado no declara
  aplicabilidad por terreno, así que la respuesta no cambia entre terrenos.
- No es una **conclusión legal** ni una comprobación de elegibilidad.
- No prometas **exactitud general**, tiempos de respuesta ni cobertura fuera de la PAC 2026.
- No prometas que la actualización revisada cambia el conocimiento: en el ensayo no lo cambia.

## Si algo no sale

| Ves | Qué significa | Qué hacer |
|---|---|---|
| `SKIP  Service: /health and /ready answer: the service is not reachable.` | El servicio no está arrancado. | `./scripts/init.sh --local-rag-start` y repite el ensayo. |
| `SKIP  Service: ... the service is running but not ready.` | El servicio está arrancado pero aún no puede responder. | Espera un minuto y repite el ensayo. |
| `FAIL  Grounded answer: ...` | La respuesta general no trae fuentes aprobadas o no es de alcance general. | No hagas la demostración; enseña el `Result:` a un desarrollador. |
| `FAIL  Trap abstention: ...` | La pregunta trampa respondió en vez de abstenerse. | No uses esa pregunta; enseña el `Result:` a un desarrollador. |
| `FAIL  Reviewed update: ...` | El paso de revisión no se comportó como debe. | No expliques la actualización; enseña el `Result:` a un desarrollador. |
| `Result: the demo rehearsal did not run. Run ./scripts/init.sh --local-rag-setup.` | Faltan las herramientas locales. | Sigue [Set up the local answer tools](owner-guide/local-answer-service.md#set-up-the-local-answer-tools). |

El ensayo no arranca nada y no toca tus terrenos ni el conocimiento aprobado. Puedes repetirlo
las veces que quieras.
