# 🫒 Manijero — Documento de Requisitos de Producto (PRD)

**Versión:** 3.1 · **Fecha:** Octubre 2026 · **Estado:** MVP Definido (Android y Desktop KMP)

---

## 1. Visión y Resumen del Producto

**Manijero** es una aplicación móvil y de escritorio desarrollada en **Kotlin Multiplatform (KMP) con Compose Multiplatform**, diseñada específicamente para personas con baja experiencia digital que poseen o gestionan uno o más terrenos de olivar (pequeños y medianos agricultores en Andalucía, especialmente en la provincia de Jaén).

### Propuesta de Valor
* **Asistente de IA conversacional** en español sencillo, estrictamente basado en fuentes oficiales verificadas (BOE, BOJA, FEGA, MAPA), sin inventar plazos ni importes.
* **Gestión local de múltiples terrenos** (secano/regadío, conventional/ecológico) para ofrecer respuestas contextualizadas a la realidad de la explotación del usuario.
* **Transparencia y seguridad jurídica:** citas literales, fechas de verificación visibles y derivación clara a las Oficinas Comarcales Agrarias (OCA) o cooperativas locales.

---

## 2. Alcance del MVP (Producto Mínimo Viable)

| En Alcance (MVP) | Fuera de Alcance (MVP / Fases Posteriores) |
|---|---|
| Chat de IA guiado por RAG con fuentes oficiales y citas | Versión para iOS (código preparado en `commonMain`, pero sin empaquetado MVP) |
| Gestión local básica de múltiples terrenos (añadir, ver, editar, borrar) | Sincronización en la nube, cuentas de usuario y perfiles compartidos |
| Contexto automático de terrenos o clarificación cuando la respuesta difiere | Gestión integral de empresa, contabilidad o trabajadores |
| Soporte multiplataforma Android (APK) y Desktop (JVM) | Mapas SIGPAC complejos, subida de documentos o fotos para peritaje |
| Modo Claro y Modo Oscuro accesibles y de alto contraste | Entrada por voz y agentes autónomos en tiempo de ejecución |

---

## 3. Arquitectura de Pantallas y Flujos de Usuario

La aplicación cuenta con una barra de navegación inferior fija de 3 pestañas accesibles y claras:

1. **Mis Terrenos (Pantalla por defecto / Inicio):**
   * Vista general con resumen de parcelas.
   * Estado vacío optimizado con ilustración en tonos oliva/tierra y llamada a la acción clara (*"Añadir primer terreno"*).
   * Tarjetas individuales para cada olivar con indicador de régimen (Secano/Regadío), variedad y opciones de edición/borrado.

2. **Asistente:**
   * Interfaz de chat moderna y limpia.
   * Tarjeta superior informativa del Asistente con sello oficial verificado.
   * Burbujas de mensajes diferenciadas (usuario a la derecha, bot con respuestas estructuradas y tarjetas de fuentes oficiales / avisos a la izquierda).
   * Campo de entrada de texto optimizado en la parte inferior sobre la barra de navegación.

3. **Ayuda y Límites:**
   * Centro de ayuda y cobertura (*"¿Qué cubre Manijero?"*).
   * Explicación clara de exclusiones y límites legales.
   * Enlaces directos a Oficinas Comarcales Agrarias (OCA) y Directorio de Cooperativas y Almazaras Locales.

---

## 4. Requisitos Técnicos y de Datos

* **Stack:** Kotlin Multiplatform, Compose Multiplatform, Ktor Client, FastAPI backend, ChromaDB + BM25, Gemini Flash (T=0) con validación estricta y cascada de seguridad.
* **Privacidad (Local-First):** Los datos de los terrenos se almacenan localmente en el dispositivo. Se envían al servidor únicamente los atributos mínimos estrictamente necesarios para responder a la consulta del usuario, evitando nombres propios o notas personales por defecto.
* **Sistema de Diseño:** Definido en el sistema *Manijero Design System* (Modo Claro con tonos verdes suaves sobre superficies marfil y Modo Oscuro con tonos carbón y oliva profundo para uso nocturno).
