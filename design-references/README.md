# Stitch design references

This is a design handoff/reference archive, not a second implementation or a product/spec authority. Each screen directory contains `screen.png` and its Stitch-generated `code.html`; the two design-system directories contain their own `DESIGN.md`. The archive also includes `manijero_prd_oficial.md`.

## Screen inventory and current contract owners

| Reference directory | Design intent | Existing feature contract(s) to consult |
|---|---|---|
| `stitch/asistente_pac_1/`, `stitch/asistente_pac_2/` | Assistant/chat screen explorations | `chat_home`, `suggested_questions`, `chat_question_submission`, `response_states`, `answer_source_cards`, `network_error_recovery`, `chat_accessibility` |
| `stitch/asistente_pac_modo_oscuro/` | Dark chat exploration | Same chat contracts; dark theme remains unverified/not specified |
| `stitch/mis_terrenos/` | Saved lands list | `land_list`, `edit_land`, `remove_land`, `land_form_accessibility` |
| `stitch/mis_terrenos_vac_o/` | Empty lands state | `land_list`, `add_land` |
| `stitch/mis_terrenos_modo_oscuro/`, `stitch/mis_terrenos_vac_o_modo_oscuro/` | Dark list and empty-state explorations | Same lands contracts; dark theme remains unverified/not specified |
| `stitch/ayuda_y_l_mites/` | Help, coverage, and limits | `coverage_and_help`, `land_data_disclosure` |
| `stitch/ayuda_y_l_mites_modo_oscuro/` | Dark help exploration | Same help contracts; dark theme remains unverified/not specified |

The screens overlap existing MVP surfaces, so this import does **not** add duplicate screen features. The separate shared theme/token foundation is planned as `shared_design_system`; it does not change the status of those screen features. If a future design implementation reveals a genuinely new behavior, first create its contract through the normal feature-spec workflow.

## Safe use by future agents

1. Read `DESIGN.md` and the owning feature spec before implementing a referenced screen.
2. Use screenshots for visual direction and HTML only to inspect the export; neither is production Compose code.
3. Resolve behavior and scope from current feature specs, `CONTEXT.md`, and `CONSTRAINTS.md`, not from the bundled PRD/masterplan where they diverge.
4. Do not copy the archive's proposed palette, fonts, spacing, navigation, or dark theme into the app without explicit design approval and appropriate theme/accessibility/spec updates. `DESIGN.md` and the shared theme are current implementation guidance.
5. Keep shared product UI in `shared/src/commonMain` per `ARCHITECTURE.md`.
