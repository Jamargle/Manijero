# Cobertura PAC Andalucía 2026 — Aprobada

## Estado

Diego verificó las copias oficiales originales, sus huellas digitales (SHA-256) y aprobó los pasajes literales de las fuentes oficiales el 2026-10-17. El catálogo de fuentes (`knowledge/source_catalog.json`) y el conjunto de pasajes canónicos (`knowledge/passages.json`) están debidamente registrados y validados. El servicio `/ask` dispone de cobertura oficial aprobada para los tres temas procedimentales de la Solicitud Única andaluza de 2026.

## Temas soportados

La cobertura de respuestas se limita a la Solicitud Única andaluza de 2026:

- Canal ordinario de presentación mediante la herramienta informática SGA a través de Entidades Reconocidas, preservando la excepción nacional para personas físicas sin acceso fehaciente a medios electrónicos;
- Fecha final de presentación de la solicitud (ampliada hasta el 15 de mayo de 2026);
- Fecha separada de modificación o inclusión de intervenciones a una solicitud presentada (ampliada hasta el 15 de junio de 2026).

Las fuentes oficiales aprobadas, ubicaciones y pasajes literales están registrados en [knowledge/source_catalog.json](../knowledge/source_catalog.json) y [knowledge/passages.json](../knowledge/passages.json).

## Ampliación del corpus (2026-11-07)

Diego revisó y aprobó el paquete `8c7b2e22…07b9` el 2026-11-07. La fusión controlada añadió 3 fuentes oficiales y 5 pasajes literales. El mismo día, Diego aprobó el paquete `dfa5f081…3128`, que retiró 1 fuente y 2 pasajes porque empeoraban las respuestas de los casos revisados (coincidencia de estado 13/14 antes, 8/14 con los cinco pasajes, 13/14 con los tres que se mantienen). El corpus queda en 6 fuentes y 7 pasajes:

- Real Decreto 1047/2022 (BOE): definición de recinto SIGPAC (art. 2.1.h);
- Ley 39/2015 (BOE): preferencia por la notificación electrónica (art. 41.1) y rectificación de errores materiales (art. 109.2).

Retenidos (revisados, no publicados por ahora): la definición de parcela SIGPAC (RD 1047/2022, art. 2.1.g) y la alegación SIGPAC en la solicitud única (Orden de 24 de marzo de 2023, art. 4.2). Desplazaban los pasajes de plazos y canal en la búsqueda; pueden volver en un paquete posterior.

Cuatro documentos revisados no se añadieron y dos se retuvieron; el motivo de cada uno consta en la tabla de veredictos. Estos pasajes aún no tienen casos de evaluación propios y el índice no se ha regenerado: hasta la reindexación y publicación separadas, ninguna versión publicada los usa. No amplían la cobertura a elegibilidad individual, importes ni notificaciones individuales.

### Veredictos de la revisión inicial (2026-11-06)

| Id | Veredicto | URL oficial | Base |
|---|---|---|---|
| `rd_1047_2022` | `added` | `https://www.boe.es/buscar/doc.php?id=BOE-A-2022-23047` | Original text; art. 2.g/h wording also appears unchanged in the consolidated copy last updated 20/11/2025. |
| `rd_1049_2022` | `not_added` | `https://www.boe.es/buscar/doc.php?id=BOE-A-2022-23049` | In force, but conditionality is a pinned "not yet covered" disclosure topic; adding a passage would contradict the copy. |
| `rd_1054_2022` | `not_added` | `https://www.boe.es/buscar/doc.php?id=BOE-A-2022-23054` | In force, but SIEX and the digital notebook are a pinned "not yet covered" disclosure topic; adding a passage would contradict the copy. |
| `orden_2023_03_24` | `added`, retenido el 2026-11-07 | `https://www.juntadeandalucia.es/boja/2023/61/4` | Original text; art. 4.2 is the SIGPAC alegación step for the single application, untouched by the BOJA 2023/80 correction. |
| `orden_2023_03_24_correccion` | `not_added` | `https://www.juntadeandalucia.es/boja/2023/80/1` | Corrects arts. 46–51 of the Order, unrelated to the selected art. 4.2; establishes no independent provision, so it is recorded as evidence only. |
| `fega_res_2026_05_20` | `not_added` | `https://www.fega.gob.es/es/noticias/node-16804` | News item announcing a deadline of 15/06/2026 that has passed; the extension is consolidated in the already-approved RD 537/2026. |
| `ley_39_2015` | `added` | `https://www.boe.es/buscar/doc.php?id=BOE-A-2015-10565` | Original text; art. 41.1 and 109.2 wording also appears unchanged in the consolidated copy last updated 06/11/2024. |

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
| `tema-fuera-de-alcance` | límite | 1 | se abstiene correctamente (guardia de alcance) |
| `reclamacion-fuera-de-alcance` | límite | 1 | se abstiene correctamente (guardia de alcance) |
| `alcance-terrenos` | límite | 1 | responde igual para todos los terrenos; no procede aclaración |

Totales: **14 casos**, **3 temas** (9 casos) y **5 límites** (5 casos). De los 11
casos que esperan respuesta, 11 responden, 8 coinciden en fuente y pasaje y 9
coinciden en la frase crítica literal. De los 3 casos que esperan abstención, los 3 se
abstienen y no hay respuestas inesperadas. No hay casos de aclaración de terrenos: el corpus aprobado
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
  `plazo` con el corpus; la guardia de alcance (`question_scope_guard`) ahora se
  abstiene antes de la recuperación. La guardia es léxica: una paráfrasis no
  listada aún puede llegar a la recuperación.

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
