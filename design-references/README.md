# Stitch design references

This is a design handoff/reference archive, not a second implementation or a product/spec authority. Each screen directory contains `screen.png` and its Stitch-generated `code.html`; the two design-system directories contain their own `DESIGN.md`. The archive also includes `manijero_prd_oficial.md`.

## Screen inventory and current contract owners

| Reference directory | Design intent | Existing feature contract(s) to consult |
|---|---|---|
| `stitch/asistente_pac_1/`, `stitch/asistente_pac_2/` | Assistant/chat screen explorations | `chat_home`, `suggested_questions`, `chat_question_submission`, `response_states`, `answer_source_cards`, `network_error_recovery`, `chat_accessibility` |
| `stitch/asistente_pac_modo_oscuro/` | Dark chat exploration | Same chat contracts; dark palette approved, screen evidence still pending |
| `stitch/mis_terrenos/` | Saved lands list | `land_list`, `edit_land`, `remove_land`, `land_form_accessibility` |
| `stitch/mis_terrenos_vac_o/` | Empty lands state | `land_list`, `add_land` |
| `stitch/mis_terrenos_modo_oscuro/`, `stitch/mis_terrenos_vac_o_modo_oscuro/` | Dark list and empty-state explorations | Same lands contracts; dark palette approved, screen evidence still pending |
| `stitch/ayuda_y_l_mites/` | Help, coverage, and limits | `coverage_and_help`, `land_data_disclosure` |
| `stitch/ayuda_y_l_mites_modo_oscuro/` | Dark help exploration | Same help contracts; dark palette approved, screen evidence still pending |

The screens overlap existing MVP surfaces, so this import does **not** add duplicate screen features. The shared theme/token foundation is `shared_design_system`; the palette refresh is planned in [`docs/design/ui-refresh-plan.md`](../docs/design/ui-refresh-plan.md) and does not change the status of those screen features. If a future design implementation reveals a genuinely new behavior, first create its contract through the normal feature-spec workflow.

## Palette authority

The winning palette is the `colors:` token block in the front matter of each design-system export: `stitch/manijero_design_system/DESIGN.md` for light and `stitch/manijero_design_system_dark_mode/DESIGN.md` for dark. Every role in those blocks is adopted verbatim in [`DESIGN.md`](../DESIGN.md) and [`docs/design/ui-refresh-plan.md`](../docs/design/ui-refresh-plan.md) §3.1 (approved 2026-10-25), except for two documented accessibility corrections: `outlineVariant` `#C2C8BD` → `#757C71` (light) and `#424942` → `#868E86` (dark), because both Stitch values fail the repository's 3:1 non-text gate.

The prose colour names in the light export (`#385E39`, `#8C6239`, `#D9A036`, `#F4F1EA`) are **not** authoritative: they contradict the same file's token table and the rendered screenshots, so they stay as written but are not adopted. Do not edit any file in this directory to match the implementation; record the approved palette and any divergence in `DESIGN.md`.

## Safe use by future agents

1. Read `DESIGN.md` and the owning feature spec before implementing a referenced screen.
2. Use screenshots for visual direction and HTML only to inspect the export; neither is production Compose code.
3. Resolve behavior and scope from current feature specs, `CONTEXT.md`, and `CONSTRAINTS.md`, not from the bundled PRD/masterplan where they diverge.
4. Do not copy the archive's fonts, spacing, navigation, or dark-theme treatment into the app without explicit design approval and appropriate theme/accessibility/spec updates. For colour, the Stitch token blocks plus `DESIGN.md` are the agreed source; `DESIGN.md` and the shared theme are current implementation guidance.
5. Keep shared product UI in `shared/src/commonMain` per `ARCHITECTURE.md`.
