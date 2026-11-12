---
name: drawio-visuals-skill
description: Create and edit native Draw.io diagrams, explain processes through concrete editable objects and visible transformations, reconstruct diagrams from source material, and inspect, patch, version, or export .drawio files. Use for diagram images and HTML previews with official-renderer QA and layout/topology checks; native .drawio files are intermediate artifacts by default.
---

# Drawio Visuals Skill

Create, reconstruct, and edit native, user-editable Draw.io files without a server, MCP, fixed template, Scene IR, or custom renderer.

## Core rules

- Treat the current `.drawio` file as the internal editable source of truth. By default deliver only per-page PNG images and one HTML preview; keep native files in an internal working directory, outside the delivery directory, and do not link them in the handoff. Deliver native files, SVG, PDF, or other formats only when explicitly requested.
- Never overwrite an input. Every mechanical write must use a new output path, including internal working files.
- Do not impose a theme, shape list, diagram type, coordinate grid, or layout recipe.
- Follow the user's specified diagram type, notation, and orientation. When these are unspecified, choose the presentation that best answers the task's actual question, including UML and non-UML forms; do not default every request to a flowchart or swimlane. Use [diagram-selection.md](references/diagram-selection.md) when choosing or substantially changing the presentation.
- For new explanatory workflows, make the objects, actions, and meaningful state or data changes visible; avoid defaulting to a chain of paragraph-filled rectangles. Use conventional symbols when they communicate better, and preserve explicit notation, source reconstruction, and the scope of local edits. Read [visual-storytelling.md](references/visual-storytelling.md) before choosing representations for a new or substantially redesigned explanatory flow; its optional native components are starting points, not a required catalog.
- For vertical flowcharts, run the main path from top to bottom, place parallel branches side by side, label exits from decision diamonds, and group supporting checks in a light gray dashed box with a plain-language purpose.
- When a central engine coordinates external modules, place the core in the center, group inputs and workers on either side, and use numbered arrows with action labels to guide the reader through one task. Where relevant, route feedback above the core, place human decisions and notification channels below it, and show an example workflow along the bottom. Choose colors to suit the subject.
- Keep arbitrary native Draw.io shapes, stencils, styles, geometry, waypoints, layers, groups, and wrapper metadata.
- Prefer a larger canvas or container over compressed nodes, labels, or routing corridors. A collision-free file is not necessarily spacious, legible, or well composed.
- Budget connector-label space before placing adjacent nodes. Long labels must fit between the connected shapes with visible clearance, or use explicit line breaks/another clear label position. Resolve endpoint-label risks and check actual rendered text bounds before marking a diagram ready; see [connector-label clearance](references/layout-authoring.md#connector-label-clearance).
- For newly authored or substantially redesigned content, set native `flowAnimation=1` on directed semantic-flow edges by default, including normal, secondary, data, exception, and retry flows. Keep references, annotations, containment, grouping, and purely structural relationships static. Let explicit user intent override this policy.
- Preserve unrelated animation styles during a local edit unless animation normalization is requested. If motion obscures hierarchy, make lower-priority semantic flows static during rendered QA instead of changing their topology.
- Treat connector animation as a visual effect, never as routing or collision avoidance.
- Use the bundled CLI only for inspect, query, patch, validate, layout/topology checks, Desktop/Web export orchestration, companion HTML, page CRUD, version listing, publish, and restore. It does not author, lay out, or implement a renderer; `render` delegates to Draw.io Desktop, `web-svg-bridge` delegates one selected page to official Draw.io Web, and preview HTML delegates to the official remote viewer.
- Treat `<base>-vNNN` as a logical delivery version shared by its images and HTML, not every internal write. Native versioning remains internal unless source delivery is requested. By default, one user-approved change consumes at most one new sibling version.
- Keep every public CLI `--page-index` zero-based, matching the `index` returned by `inspect`. Prefer stable page IDs for multi-page work.
- Limit each document to 15 pages. The CLI rejects larger existing documents and additions beyond this limit with `PAGE_COUNT_LIMIT`; never truncate pages to satisfy it.
- Do not enable this Skill alongside the official `drawio@drawio` Skill; this Skill already carries the same native Mermaid/XML authoring path.

## Choose the presentation

Separate the diagram type from the authoring tool. Choose by what the reader needs to understand: progression, responsibilities, interactions, states, structure, deployment, data movement, or comparison. A supplied diagram, explicit format, or requested local edit constrains that choice. When the user leaves it open, make the choice autonomously, briefly explain it when useful, and proceed; do not make the user select from a catalog. Read [diagram-selection.md](references/diagram-selection.md) for the question-to-form guide and tradeoffs.

Carry the user's visual-expression requirements across every page and later revision. A change to swimlanes, states, or another diagram type does not reset a request for concrete graphics. For a pictorial explanation, every main object or materially different state must have a recognizable editable construction that carries its identity or change; a captioned rectangle or the same decorative icon repeated everywhere does not satisfy that request. Preserve formal semantics through boundaries, transitions, guards, and relationships while illustrating state contents where compatible. Do not add a plain-text companion page as a substitute for the requested visual treatment.

Then choose objects and notation appropriate to that presentation. Concrete illustrations can explain payloads and transformations, while formal UML, ER, and other established symbols should retain their semantic conventions. Do not treat every labeled class, state, or schema box as a text-heavy-flow defect.

## Choose the workflow

| Request | Workflow |
|---|---|
| Create a standard diagram | Mermaid → Draw.io Desktop → `.drawio` |
| Create with custom shapes/styles/positions | Direct native XML → `.drawio` |
| Explain a process with concrete objects or swimlanes | Evidence/ownership → visual-storytelling → native objects and transformations → official-renderer QA |
| Create from PDF or text | Read source → extract supported structure → Mermaid/XML |
| Reconstruct from an image | Inspect at original resolution → editable native cells → optional preview comparison |
| Check visual conflicts | `check-layout` → Desktop `render` → inspect image → small patch → rerender; fall back to Viewer HTML |
| Check a business flow | `check-topology` with known starts, terminals, and required edges |
| View without Desktop | `preview` → companion `.html` with visible page count/names using the official remote viewer |
| Export SVG without Desktop | Prefer one `web_svg_session.py` loopback session; retain `web-svg-bridge → commit-web-svg` for manual recovery |
| Export or apply a requested layout | Create `.drawio` first → Draw.io Desktop CLI |
| Edit, target unknown | `inspect → query → patch` |
| Edit, page and cell ID known | `query → patch` |
| Edit, fresh trusted CLI result already has revision and target | `patch` |
| Add, rename, or delete a page | `inspect → page add/rename/delete` |
| List or restore a file version | `versions` or `versions → inspect old → restore` |
| Publish a completed working file | `inspect working → publish` |
| View one or more known cells | `query` |
| Independently check a file | `validate` |

Read [references/authoring.md](references/authoring.md) for creation, preview, Desktop detection, layout, and export. Read [references/web-svg-export.md](references/web-svg-export.md) only when Desktop is unavailable and explicitly requested SVGs must be exported through official Draw.io Web. Read [references/layout-authoring.md](references/layout-authoring.md) when authoring a crowded diagram, maintaining cross-page visual consistency, interpreting `check-layout`, or performing rendered visual QA. Read [references/topology.md](references/topology.md) when a process, lifecycle, or request path must be connected. Read [references/source-to-diagram.md](references/source-to-diagram.md) when the source is PDF, text, or an image. Read [references/drawio-xml.md](references/drawio-xml.md) only for direct XML authoring. Read [references/patch-contract.md](references/patch-contract.md) before constructing a patch. Read [references/versioning.md](references/versioning.md) for page commands and immutable history.

## Plan a logical delivery

- Before writing, map every requested change to its page/cell, required decision exits, critical start/terminal/edge constraints, side effects or error paths, terminology, and all affected pages.
- For new multi-page documents, define document-local visual roles before authoring and reuse page foundations, typography, repeated component styles, and relationship styling across pages. When adding or editing content, inherit the existing document convention within the requested scope. Follow [document visual consistency](references/layout-authoring.md#document-visual-consistency) for role selection, intentional exceptions, and cross-page acceptance.
- For one atomic edit that needs no later topology, layout, or visual correction, write directly to a new internal native version.
- For multi-page edits or any task likely to need QA correction, create an Agent-owned temporary directory and write `working-01.drawio`, `working-02.drawio`, and so on. Complete all requested edits and checks there; `publish` is optional for an internal final snapshot or explicitly requested native delivery.
- Generate the delivery HTML and per-page PNGs from the same final checked native snapshot; a published `.drawio` deliverable is not required. For user-facing HTML, embed a verified render of each page with `preview --fallback-png` (repeat in page order). Check the delivered HTML with the remote Viewer blocked, including at narrow width. A successful online render alone does not verify the recipient’s preview. If no official render is available, label the HTML online-only and disclose the limitation. Temporary previews are QA artifacts, not deliverables.
- After verifying self-contained images and HTML, remove only disposable QA files created by this task; retain the final native snapshot internally for later edits. Never clean existing formal versions without explicit user authorization.

## Create

1. Read `references/authoring.md` and detect Draw.io Desktop. Prefer Mermaid for standard topology when Desktop is available; use direct native XML for precise styling, specialized shapes, source-matched geometry, or when Desktop is absent.
2. Choose a descriptive lowercase-hyphenated base, reserve `<base>-v001` for the initial image/HTML delivery and keep its `.drawio` snapshot internal, and use a new working path while QA corrections remain. Convert temporary Mermaid to native `.drawio`, or author a well-formed `mxGraphModel`/`mxfile` without XML comments. Remove only the temporary Mermaid source after successful conversion.
3. Before writing geometry, read `references/layout-authoring.md`. For explanatory flows, also use `references/visual-storytelling.md` to choose meaningful objects, show transformations, and place actions in their verified owner lanes. Form a task-local composition plan and edge inventory; preserve required relationships, reserve routing space, and size nodes from their content. Do not introduce a Scene IR or persisted schema.
4. Run `check-layout` and apply the warning-specific guidance in that reference. Correct deterministic collisions; unresolved renderer-dependent findings require readable visual QA or an explicit limitation.
5. For a business flow with known starts, terminals, or required edges, run `check-topology`. Missing required edges or failed reachability block publication.
6. Inspect every page and high-risk region through Draw.io Desktop or the official Viewer, following the shared correction budget in [references/layout-authoring.md](references/layout-authoring.md#correction-budget). Export success alone is not visual acceptance. When pictorial expression is requested, apply the visual-storytelling acceptance check to every page, including companion views; a page that regresses to generic text boxes is not ready.
7. Generate per-page PNGs and companion HTML from the completed internal native snapshot as specified under **Deliver**. Verify header page switching and Viewer toolbar synchronization in multi-page previews. Without Desktop, capture the official Viewer at readable resolution, cropped to each complete diagram. Use the Web SVG fallback only for explicitly requested SVGs.

## Create from a source

Read `references/source-to-diagram.md` before converting a PDF, text file, screenshot, or reference image. Keep source interpretation flexible and evidence-bound; do not turn this workflow into a fixed diagram schema.

- Default to one page and split only when the content or user request makes multiple pages clearer.
- Reconstruct images as independently editable cells, edges, text, and groups. Do not use the full source image as a false editable result.
- Preserve the source language unless the user requests translation.
- Disclose unreadable, truncated, inferred, or visually unverified content.

## Inspect and query

Use Python 3.10 or newer:

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py inspect input.drawio
python3 -I -B <skill-root>/scripts/drawio_file.py query input.drawio --page-id PAGE --id CELL
```

- `inspect` returns the file revision, page identities, encoding, cell counts, and compact warnings.
- `query` returns compact native cell fields, geometry, and a cell hash. It never returns raw XML unless `--include-raw` is explicit.
- Narrow queries by page and cell ID when known.
- Query output is deliberately capped. Add filters instead of requesting the entire diagram.
- A revision is trusted for direct patching only when this CLI returned it in the current task for the same canonical file.

## Patch

1. Read `references/patch-contract.md`.
2. Build a small JSON patch using the fresh file revision and one page selector when the document has multiple pages.
3. Use native cell operations; do not rebuild the whole document for a local edit. Use `set-label` for labels and pass decoded logical text or HTML; never pre-escape `<`, `>`, `&`, or quotes for XML.
4. Write to a new path. A one-pass edit may write directly to a new internal native version (or a requested native deliverable):

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py patch diagram-v001.drawio patch.json --output diagram-v002.drawio
```

5. A successful patch already validates the exact output before committing it. Do not automatically run `validate` again.
6. On `REVISION_CONFLICT`, query the current file and rebuild the patch once. Stop after a second conflict.

Use `replace-cell-xml` only when field-level operations cannot express a native feature. It requires the fresh `cellHash` returned by query.

## Manage pages

Use the exact commands and selector rules in `references/versioning.md`. Get a fresh revision with `inspect`, then perform one page operation into a new output. Prefer page ID over page name. Use working files when page operations are part of a larger logical change. Page operations remain separate from Patch v1.

## Use immutable history

Native history is internal by default; publish to the delivery directory only when native source is requested. Use `versions` to list same-directory `<base>-vNNN.drawio` files. Use `publish` to copy a completed, freshly inspected working file into the chosen formal output without overwrite. To restore, inspect the chosen old version, then run `restore` into a new, higher-numbered file. Never replace a newer version with older bytes in place.

## Validate

Run validation only when the user asks to check a file or when diagnosing an invalid artifact:

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py validate input.drawio
```

Validation is read-only. It checks supported XML/compression, page structure, logical cell identity, references, geometry, and configured safety limits. It is not a visual-quality or rendering check.

For layout and rendered QA, follow `references/layout-authoring.md`. `check-layout` reports `clear`, `collision`, or `indeterminate`; use `--verbose` to locate affected cells and review regions. It never moves cells and cannot prove renderer-dependent routes, labels, or composition correct.

For business-flow connectivity, follow `references/topology.md`; explicit starts, terminals, and required edges are authoritative. Never infer a required relationship from visual proximity.

For Desktop rendering and companion HTML, use the commands and preview contract in `references/authoring.md`. Inspect the rendered result with host vision; generating an export or HTML file is not a visual check. SVG export without Desktop follows `references/web-svg-export.md`.

## Stop conditions

- Stop rather than guessing a page or cell identity.
- Stop if Python is older than 3.10.
- If Desktop is absent, author native XML and use a complete, readable official Viewer capture for PNG delivery. Do not replace a requested image with XML. Report a blocker if no official render is available. Desktop-only conversion/layout/PDF requests require the relevant dependency; explicitly requested SVGs can use the official Web fallback.
- Stop on unsupported legacy compression, unsafe wrapper structure, input/expanded-size limits, or a revision conflict after one retry.
- Stop publication when structural validation or explicit topology constraints fail. Missing rendered QA may be published only as `structure_only`, never `ready`.
- Follow the correction budget in [references/layout-authoring.md](references/layout-authoring.md#correction-budget); disclose any remaining issues after that budget.
- Stop when a PDF/image cannot be read completely enough for the requested diagram; do not install a parser/OCR dependency or invent missing content.
- Do not silently switch to in-place editing, whole-file replacement, a fixed template, or a network download.
- If a requested edit cannot be represented safely, offer a new full XML artifact and state that it is a full replacement, not a local patch.

## Deliver

- A complete default delivery contains only a PNG image for every page and one same-version `.html` with all verified PNGs embedded. Use Desktop PNG export or a complete official Viewer capture without browser chrome. Return absolute image/HTML paths, listing page images in order with their names. The HTML must work without a sibling `.drawio` file; embedded native XML for interactive viewing/editing is allowed.
- For a single page use `<base>-vNNN.png`; for multiple pages use `<base>-vNNN-page-01.png`, `-page-02.png`, and so on, plus `<base>-vNNN.html`. Native XML, generators, logs, and QA files are intermediates, not default deliverables.
- If a required image or offline HTML preview is missing, state that delivery is incomplete and name the missing outputs. SVG is optional unless explicitly requested: do not attempt its export by default, or downgrade an otherwise complete PNG/HTML delivery because SVG is unavailable. Requested SVGs must use an official renderer, never a custom SVG renderer.
- State that the source file was not modified.
- State the delivery quality as `ready`, `structure_only`, or `draft_with_issues`; never imply rendered QA occurred when it did not.
- For source-based diagrams, state any source gaps, approximations, or missing visual QA.
- Summarize page names and material limitations; include internal cell IDs only when useful for a requested source edit.
- Do not paste full XML, temporary files, or internal hashes unless the user explicitly asks.
