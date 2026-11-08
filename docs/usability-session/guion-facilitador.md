# Guion del facilitador

Sesión de uso con 2 o 3 personas con poca experiencia con ordenadores. Cada una dura unos 30 minutos. Se hace en la aplicación de escritorio **Manijero QA**, con datos inventados.

## Antes de empezar (una vez)

1. Comprueba que QA funciona: `./scripts/init.sh --qa-status`
2. Abre la aplicación: `./scripts/init.sh --desktop-qa` (ventana **Manijero QA**).
3. Imprime estos papeles: nota de consentimiento, tarjetas de tareas (recortadas), una hoja de observación por persona y las preguntas finales.

## Con cada persona

1. Prepara la aplicación (mira «Entre una persona y otra»). Que la tarjeta **Antes de empezar** se vea.
2. Lee la nota de consentimiento en voz alta y pide un «sí» de palabra. Sin firma.
3. Escribe el código (P1, P2...) en la hoja. **Nunca escribas su nombre.**
4. Di: «Probamos la aplicación, no a ti. No puedes hacerlo mal. Piensa en voz alta si quieres.»
5. Entrega las tarjetas **de una en una** y léelas en voz alta. No señales la pantalla.
6. Si la persona duda, pregunta: «¿Qué piensas que pasa ahora?». No expliques.
7. Apunta en la hoja: resultado, minutos y lo que pase.
8. Al terminar las cuatro tareas, haz las preguntas finales.

## Cuándo ayudar y cuándo parar

- **Ayuda:** solo si la persona la pide o pasan 2 minutos sin avanzar. Apunta «Necesitó ayuda».
- **Abandono:** si la persona dice que no puede o que quiere pasar, o pasan 5 minutos. Apunta «Abandonó» y sigue con la tarea siguiente.
- Puede parar en cualquier momento.

## Las cuatro tareas

1. **Primer uso.** Leer **Antes de empezar** y cerrarla con **Entendido**.
2. **Añadir dos terrenos.** Con las dos tarjetas de terrenos inventados: **Mis terrenos**, **Añadir terreno**, **Guardar terreno**.
3. **Pregunta sobre sus terrenos.** Léele la pregunta de la tarjeta y que elija el terreno cuando la aplicación se lo pida.
4. **Fuentes.** En esa respuesta, abrir **Fuentes**, decir quién publica el documento y abrir **Abrir documento oficial**.

### Atención con la tarea 3

Es posible que la aplicación **no** muestre **Elige el terreno de tu pregunta**, porque las fuentes aprobadas responden igual para todos los terrenos. No pasa nada, y no lo cuentes como un fallo de la persona. En ese caso, la tarea se completa cuando hace la pregunta y señala la línea que dice qué terrenos ha tenido en cuenta: **Tiene en cuenta todos tus terrenos.**

En la hoja marca siempre si la aplicación pidió elegir un terreno: sí o no. Así nadie lee un «sí» que no ocurrió.

## Entre una persona y otra

Se hace a mano en la aplicación **Manijero QA**:

1. En **Mis terrenos**, pulsa **Quitar** en cada terreno inventado.
2. Entra en **Terrenos eliminados** y pulsa **Borrar para siempre** en cada uno.
3. Pulsa **Ajustes**, luego **Ayuda** y luego **Ver bienvenida**, para que **Antes de empezar** vuelva a verse.

## Al terminar con cada persona

Ejecuta `./scripts/init.sh --usability-record`, con la hoja delante. Escribe el código, el resultado de cada tarea, los minutos y las notas, en minúsculas y sin nombres. Al final envía el resumen al desarrollador.

## Reglas de datos

- Nunca pidas ni escribas nombres reales, lugares reales ni datos reales de terrenos.
- Solo las tarjetas de terrenos inventados.
- No grabes voz, cara ni pantalla.
