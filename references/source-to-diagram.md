# Source-driven diagrams

Read this reference only when creating a diagram from PDF, text, a screenshot, or another reference image. Interpret the source with high freedom; the output remains native Draw.io rather than a fixed intermediate schema.

## PDF and text

1. Use the host Agent's available document or file-reading capability. Do not install or bundle a PDF parser, OCR engine, upload service, or network dependency.
2. Establish source coverage before drawing. Extract only supported titles, sections, entities, relationships, containment, order, states, and quantities.
3. Preserve the source language unless the user requests translation. Keep exact terminology where it carries domain meaning.
4. Default to one readable page. Use multiple meaningfully named pages only when the user asks or distinct sections cannot remain readable together.
5. Choose Mermaid when it expresses the topology compactly and Desktop is available. Choose direct XML for source-specific shapes, precise geometry, rich styling, or no Desktop.
6. Represent PDF content with editable shapes and text. Do not embed whole PDF pages as images.

If extraction is truncated, a page is unreadable, facts conflict, or a scanned PDF cannot be inspected visually, stop or narrow the request. Never silently invent or omit material that changes the diagram's meaning.

## Image reconstruction

1. Inspect the source at original resolution before authoring.
2. Reconstruct in this priority order: text and connections; containers and groups; relative geometry; shapes, colors, line styles, and decoration.
3. Create separate native vertices, edges, labels, wrappers, and geometry so the user can edit each meaningful element.
4. Prefer a known native stencil or an editable geometric approximation for an unknown icon. Embed a local raster fragment only when the user explicitly accepts that fragment being non-editable.
5. Treat multiple images as one result only when they describe the same diagram. Otherwise use separate pages when that improves clarity.
6. Before coordinates, inventory the source edges and preserve their endpoints, direction, labels, and containment. Apply topology compression from `layout-authoring.md` only when the user requests simplification or redesign; reconstruction alone does not authorize aggregation or removal of visible relationships. Run `check-layout --verbose` and correct material collisions before delivery; use its full-page and risk-region targets for rendered QA. For a process with known starts, terminals, or source-supported relationships, run `check-topology` with those constraints.
7. Prefer a Desktop `render` and inspect the PNG. Generate the companion HTML in all cases, and inspect the official Viewer when the host permits it. Make one correction pass for material mismatches; do not chase pixel-level fidelity unless the user asks.
8. From the final internal native snapshot, export one PNG per page through Desktop or capture each complete page from the official Viewer. Embed these images into the delivery HTML. Use the base version name for one page and `-page-01`, `-page-02`, etc. for multiple pages. SVG is exported only when requested; exports do not replace visual QA.

Do not claim pixel-perfect reproduction. When rendered QA is unavailable, state that topology, native editability, and deterministic layout findings were checked, report `structure_only`, and disclose incomplete route or label coverage.

## Deliver

- Keep every fact and label traceable to the supplied source or an explicitly stated approximation.
- Keep `.drawio` as an internal editable intermediate and use immutable version naming by default.
- Deliver only same-version HTML and per-page PNGs by default. List page names next to their image paths. Include native source or additional formats only when explicitly requested.
- Report page names, material omissions, uncertain interpretations, raster fragments, and visual-QA status.
