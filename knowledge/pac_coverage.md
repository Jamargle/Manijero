# Cobertura PAC Andalucía 2026 — Aprobada

## Estado

Diego verificó las copias oficiales originales, sus huellas digitales (SHA-256) y aprobó los pasajes literales de las fuentes oficiales el 2026-10-17. El catálogo de fuentes (`knowledge/source_catalog.json`) y el conjunto de pasajes canónicos (`knowledge/passages.json`) están debidamente registrados y validados. El servicio `/ask` dispone de cobertura oficial aprobada para los tres temas procedimentales de la Solicitud Única andaluza de 2026.

## Temas soportados

La cobertura de respuestas se limita a la Solicitud Única andaluza de 2026:

- Canal ordinario de presentación mediante la herramienta informática SGA a través de Entidades Reconocidas, preservando la excepción nacional para personas físicas sin acceso fehaciente a medios electrónicos;
- Fecha final de presentación de la solicitud (ampliada hasta el 15 de mayo de 2026);
- Fecha separada de modificación o inclusión de intervenciones a una solicitud presentada (ampliada hasta el 15 de junio de 2026).

Las fuentes oficiales aprobadas, ubicaciones y pasajes literales están registrados en [knowledge/source_catalog.json](../knowledge/source_catalog.json) y [knowledge/passages.json](../knowledge/passages.json).

## Evaluación de respuestas revisada

La evidencia de extremo a extremo de estos tres temas vive en
[`knowledge/pac_answer_eval.json`](pac_answer_eval.json), con el contrato
[`pac-answer-eval-v2`](pac_answer_eval.schema.json). Es una muestra pequeña de
preguntas sintéticas, ancladas en los pasajes aprobados y revisadas **solo por el
autor del proyecto** (Diego, 2026-10-27). No es una revisión legal independiente,
no es un estudio de usuarios y no demuestra calidad general de las respuestas.
Los resultados son informativos: no hay umbral numérico ni puerta de calidad.

### Matriz de cobertura

| Área | Tipo | Casos | Resultado |
|---|---|---|---|
| `canal-presentacion` | tema | 3 | 2 correctos; 1 cita otro plazo |
| `plazo-presentacion` | tema | 2 | 2 correctos |
| `plazo-modificacion` | tema | 4 | 3 correctos; 1 cita otro plazo |
| `distincion-fechas` | límite | 1 | cita el plazo de modificación, no aclara la premisa |
| `campana-fuera-de-alcance` | límite | 1 | se abstiene correctamente |
| `tema-fuera-de-alcance` | límite | 1 | se abstiene correctamente |
| `reclamacion-fuera-de-alcance` | límite | 1 | responde con un plazo no solicitado |
| `alcance-terrenos` | límite | 1 | responde igual para todos los terrenos; no procede aclaración |

Totales: **14 casos**, **3 temas** (9 casos) y **5 límites** (5 casos). De los 11
casos que esperan respuesta, 11 responden, 8 coinciden en fuente y pasaje y 9
coinciden en la frase crítica literal. De los 3 casos que esperan abstención, 2 se
abstienen y 1 responde. No hay casos de aclaración de terrenos: el corpus aprobado
no declara `applicability`, así que la respuesta no cambia entre terrenos; la
aclaración mixta sigue cubierta por `land_safety_eval`, no por este conjunto PAC.

Casos concretos (el informe conserva cada fallo visible):

- `canal-sga-2026` (tema 1): la recuperación léxica devuelve el pasaje del plazo
  de presentación, no el del canal SGA; el pasaje del canal no comparte tokens
  exactos con la pregunta (`solicitud`/`solicitudes`, `presento`/`presentarán`).
  Queda como límite conocido.
- `fecha-modificacion-2026` (tema 3): el pasaje del plazo de presentación queda
  primero y el de modificación segundo; el presupuesto de respuesta conserva solo
  la primera afirmación. Queda como límite conocido.
- `distingue-fechas-2026` (límite): la pregunta niega la fecha de presentación,
  pero la recuperación prioriza el pasaje de modificación y no corrige la premisa.
  Queda como límite conocido.
- `reclamacion-fuera-de-alcance` (límite): una reclamación no cubierta comparte
  `plazo` con el corpus y recibe el plazo de modificación. Queda como límite
  conocido de relevancia; el informe lo cuenta como respuesta inesperada, nunca
  como acierto.

Defecto corregido en este cambio: dos afirmaciones extractivas podían unirse en
una sola frase cuando el primer pasaje no terminaba en punto, y la segunda
afirmación le prestaba sus reglas de cifra y literalidad. Ahora cada afirmación se
separa en una línea antes de verificar; el caso
`canal-excepcion-persona-fisica-2026` responde con el pasaje nacional de excepción.

Omisiones fuera de alcance, sin casos que las conviertan en cobertura:
elegibilidad individual, importes de ayudas, penalizaciones por mora,
notificaciones individuales, adaptaciones por controles de monitorización,
reclamaciones y recursos, fuerza mayor y otras campañas. El conjunto de casos
declara esta lista y el informe la repite.

Comando con entradas fijas (`--active-campaign 2026 --as-of 2026-10-26 --k 5`):

```sh
backend/.venv/bin/python backend/scripts/evaluate_pac_answers.py \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json \
  --active-campaign 2026 --as-of 2026-10-26 --k 5
```

Dos ejecuciones idénticas producen el mismo informe. Este informe no afirma
corrección legal ni cubre preguntas fuera de los casos enumerados.

## Exclusiones

Elegibilidad individual, importes de ayudas, penalizaciones por mora, notificaciones individuales, adaptaciones por controles de monitorización, reclamaciones, recursos, fuerza mayor y otras campañas quedan fuera de alcance. No se afirma que ningún terreno o persona reúna requisitos.

Revisor: **Diego**. Aprobación de candidatos, temas y exclusiones: **2026-10-17**. Aprobación de pasajes literales y verificación de copias oficiales: **2026-10-17 (Aprobada)**.
