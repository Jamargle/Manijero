# Stitch design references

This is a design handoff/reference archive, not a second implementation or a product/spec authority.
The screen directories contain explorations (`screen.png` and Stitch-generated `code.html`); the
design-system directories and `manijero_prd_oficial.md` are historical exports. Current UI guidance
is in [`DESIGN.md`](../DESIGN.md), and behavior belongs to the linked feature contracts.

## Screen inventory and current contract owners

| Reference directory | Design intent | Existing feature contract(s) to consult |
|---|---|---|
| `stitch/asistente_pac_1/`, `stitch/asistente_pac_2/` | Assistant/chat screen explorations | `chat_home`, `suggested_questions`, `chat_question_submission`, `response_states`, `answer_source_cards`, `network_error_recovery`, `chat_accessibility` |
| `stitch/asistente_pac_modo_oscuro/` | Dark chat exploration | Same chat contracts; consult their acceptance records for current evidence and limits |
| `stitch/mis_terrenos/` | Saved lands list | `land_list`, `edit_land`, `remove_land`, `land_form_accessibility` |
| `stitch/mis_terrenos_vac_o/` | Empty lands state | `land_list`, `add_land` |
| `stitch/mis_terrenos_modo_oscuro/`, `stitch/mis_terrenos_vac_o_modo_oscuro/` | Dark list and empty-state explorations | Same lands contracts; consult their acceptance records for current evidence and limits |
| `stitch/ayuda_y_l_mites/` | Help, coverage, and limits | `coverage_and_help`, `land_data_disclosure` |
| `stitch/ayuda_y_l_mites_modo_oscuro/` | Dark help exploration | Same help contracts; consult their acceptance records for current evidence and limits |

The screens overlap existing MVP surfaces, so this import does **not** add duplicate screen features.
The shared theme/token foundation is `shared_design_system`; the linked contracts own each screen.
[`docs/design/ui-refresh-plan.md`](../docs/design/ui-refresh-plan.md) is a historical planning record,
not current status. If a future design change adds behavior, create its contract through the normal
feature-spec workflow.

## Palette authority

The design-system exports' `colors:` blocks are palette provenance. The current palette and its two
accessibility corrections are recorded in [`DESIGN.md`](../DESIGN.md); the historical plan is not a
second palette authority. `outlineVariant` changes from `#C2C8BD` to `#757C71` (light) and `#424942`
to `#868E86` (dark), because the export values fail the repository's 3:1 non-text gate.

The prose colour names in the light export (`#385E39`, `#8C6239`, `#D9A036`, `#F4F1EA`) are **not** authoritative: they contradict the same file's token table and the rendered screenshots, so they stay as written but are not adopted. Do not edit any file in this directory to match the implementation; record the approved palette and any divergence in `DESIGN.md`.

## Safe use by future agents

1. Read `DESIGN.md` and the owning feature spec before implementing a referenced screen.
2. Use screenshots for visual direction and HTML only to inspect the export; neither is production Compose code.
3. Resolve behavior and scope from current feature specs, `CONTEXT.md`, and `CONSTRAINTS.md`, not from the bundled PRD/masterplan where they diverge.
4. Do not copy the archive's fonts, spacing, navigation, or dark-theme treatment into the app without explicit design approval and appropriate theme/accessibility/spec updates. For colour, the Stitch token blocks plus `DESIGN.md` are the agreed source; `DESIGN.md` and the shared theme are current implementation guidance.
5. Keep shared product UI in `shared/src/commonMain` per `ARCHITECTURE.md`.
