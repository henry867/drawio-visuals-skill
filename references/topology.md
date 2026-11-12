# Directed topology checks

Use this reference when a workflow, lifecycle, request path, or state transition must be connected. `check-topology` reads native `mxCell` source/target references; it does not infer relationships from coordinates and does not create a Scene IR.

Before authoring a new or substantially redesigned topology, use the task-local P0–P3 priority and semantic-flow/static-kind inventory in `layout-authoring.md`. Aggregate four or more repeated same-protocol, same-boundary, or same-target links when their individual edges add no distinct meaning. Preserve source-supported direct edges required by `--expect-edge`; compression must not fabricate a serial chain or erase a critical relationship.

## Choose constraints

- Pass every known entry node with repeatable `--start`.
- Pass every accepted terminal with repeatable `--terminal`.
- Pass critical relationships with repeatable `--expect-edge SOURCE TARGET`. `SOURCE:TARGET` is also accepted for IDs without `:`.
- Select one page when a multi-page file has constraints. Prefer `--page-id`.
- Use IDs returned by `query`; do not invent an ID from a visible label.

Example:

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py check-topology diagram.drawio \
  --page-id main \
  --start webhook \
  --terminal done --terminal human --terminal skipped \
  --expect-edge status-gate timer \
  --expect-edge redis-dedupe user-context
```

The default output is a compact summary. Add `--verbose` only when complete component and cell-ID evidence is needed. Add `--require-connected` only when the selected page is required to contain one weakly connected business topology.

## Interpret findings

- `MISSING_EXPECTED_EDGE`: a required direct relationship is absent. Treat as blocking.
- `UNREACHABLE_FROM_START`: at least one vertex cannot be reached from any declared start. Treat as blocking unless the constraint is wrong.
- `CANNOT_REACH_TERMINAL`: a vertex in the checked start scope cannot reach an accepted terminal. Treat as blocking unless an intentional endless loop is documented.
- `ISOLATED_CONSTRAINT_VERTEX`: an explicitly declared start or terminal has no valid incident edge. Treat as blocking.
- `DISCONNECTED_TOPOLOGY`: directed edges form multiple weak components. It is advisory by default because independent subflows may be intentional; `--require-connected` makes it blocking.
- `ISOLATED_VERTEX`: a vertex has no incident native edge. Titles, notes, lanes, and decorative vertices commonly appear here; this is advisory.
- `NO_INCOMING_EDGE` / `NO_OUTGOING_EDGE`: non-start/non-terminal vertices lack a direction. These are advisory because a page may contain independent fragments.
- `FLOATING_OR_NON_VERTEX_EDGE`: an edge uses explicit points or non-vertex endpoints and is outside directed reachability checks.
- `DUPLICATE_EDGE_PAIR`: multiple native edges connect the same ordered pair. Confirm that this is intentional.

Do not make all automatic findings blocking. Explicit start, terminal, and expected-edge failures are authoritative; unconstrained component and degree findings require Agent judgment. Run `check-layout` separately because connectivity does not prove readable routing.

Reachability uses topology vertices only: vertices incident to valid directed edges plus explicit start/terminal/expected-edge endpoints. Completely isolated, unconstrained titles, notes, legends, and lane containers remain visible in isolated advisory counts but are not reported as unreachable. The checker does not infer decoration roles from styles or labels.
