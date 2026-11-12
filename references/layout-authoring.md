# Flexible layout authoring and rendered QA

Use this reference for crowded diagrams, cross-page visual consistency, `check-layout` interpretation, or rendered visual QA. These are risk-based heuristics, not templates, fixed spacing, or a layout engine.

## Choose meaningful representations before coordinates

For explanatory flows, use [visual-storytelling.md](visual-storytelling.md) to identify the flowing objects, the actions, the visible transformations, and verified ownership before choosing node shapes. A uniform chain of text-heavy rectangles is not the default representation. Preserve explicit notation and source fidelity; optional component examples do not impose a palette or layout.

If the type is not specified, select it using [diagram-selection.md](diagram-selection.md) before laying out the graph. The user's requested type/orientation takes precedence; UML and non-UML forms remain available. Compose according to the chosen form's semantics rather than treating every diagram as a runtime sequence.

For swimlanes, horizontal lanes place roles in rows and progress normally runs left to right; vertical lanes place roles in columns and progress normally runs top to bottom. Keep composite graphics upright during orientation changes and distinguish an initiator, event publisher, consumer, and storage owner.

## Compress topology before coordinates

Create a short task-local edge inventory before drawing. Do not persist it as Draw.io metadata, a Scene IR, or a reusable schema.

The compression guidance in this section applies to new diagrams or requested simplification/redesign. For source-image reconstruction, preserve the source topology and relative composition by default; do not aggregate or omit visible relationships to satisfy these heuristics.

- Classify priority as P0 core runtime/control calls, P1 key artifact reads or writes, P2 supporting administration or management, and P3 redundant explanation.
- Start with P0 and P1. Add P2 only when it materially changes the user's understanding. Express P3 through a node label, container title, note, or legend instead of another connector.
- Classify kind separately as semantic flow, reference, annotation, or containment/grouping. Priority does not decide animation; kind does.
- Aggregate four or more same-protocol, same-boundary, or same-target relationships through a shared bus, boundary node, or container relationship when individual edges repeat the same fact.
- Show Dispatcher, Handler, or Controller fan-out as parallel consumers. Do not turn sibling consumers into a serial call chain without source evidence.
- Compression is an authoring decision. The CLI does not delete, reconnect, or reinterpret existing topology.

## Document visual consistency

Before authoring a new multi-page document, define one task-local visual convention and reuse it across pages. Include only roles the content needs, with values chosen for this document; do not impose a global theme, palette, type scale, fixed layout, or permanent schema.

- **Page foundations:** reuse the background treatment, page-edge margins, and title-area alignment and spacing. Inspect both `mxGraphModel` background and any full-page background cells; changing the outer HTML background alone does not unify native pages. Keep deliberate transparency when it is part of the convention.
- **Typography:** define roles such as page title, subtitle, section heading, body, and caption or footnote. Reuse each role's font family with suitable language fallbacks, size, weight, and color. Identify roles from meaning and hierarchy, not font size, position, or cell ID alone; small text can have different roles.
- **Repeated components:** give cards, containers, badges, and legends with the same role consistent fills, borders, corner treatment, and internal padding. Reuse styling rather than forcing identical dimensions, coordinates, or arrangements; content determines size and diagram semantics determine layout.
- **Relationships:** use consistent colors, stroke widths, dash patterns, and arrow conventions for the same meaning. Preserve distinctions such as calls versus dependencies and respect native shape/perimeter behavior. Follow the existing semantic-flow animation policy; style consistency does not justify changing endpoints, direction, or topology.

New pages and edited elements inherit the corresponding document roles. For existing mixed styles, inspect comparable pages to establish the intended convention; do not automatically treat the first page or most common style as authoritative. Preserve unrelated styles during local edits, and preserve source styling during faithful reconstruction unless normalization or redesign is requested.

Keep intentional cover treatments, section accents, business-category colors, and semantic status colors as explicit task-local exceptions. An exception needs a design or semantic reason; fitting crowded content is not one. Different diagram types may use different compositions while sharing the document's visual foundations.

Apply the choices to native page/cell styles and geometry. For text, inspect `fontFamily`, `fontSize`, `fontStyle`, `fontColor`, and rich-text inline overrides; preserve other emphasis flags when changing weight. Adjust boxes, wrapping, and surrounding space instead of shrinking one page's text. Regenerate HTML and requested images from the corrected internal native version; outer companion HTML CSS is not a substitute for correcting the diagram.

Before delivery, compare backgrounds, margins/title areas, and corresponding text, component, and relationship roles across the pages in scope against the chosen convention and recorded exceptions. Inspect effective styles, including background cells and inline overrides; neither `validate` nor `check-layout` checks this cross-page convention. Then compare official renders at the same zoom scale, checking consistency, contrast, wrapping, clipping, and readability at the intended viewing scale. Fit-to-page views of differently sized canvases may make equal source sizes look different; distinguish that from a style mismatch and do not compensate by changing individual page fonts. Retain content-driven canvas sizes unless a uniform presentation size is requested. Disclose unverified rendering when only source styles could be checked.

## Compose space before authoring cells

Form a short task-local composition plan before writing coordinates. Do not persist it as Scene IR, a schema, or a reusable template.

1. Choose the reading direction and primary visual spine from the task semantics.
2. Separate the primary spine, branch outcomes, error/exception outcomes, and annotations into distinct spatial bands when they would otherwise compete for one corridor.
3. Size nodes from their actual labels before positioning them. Prefer a wider/taller node over squeezed text or a smaller font.
4. Reserve labeled routing corridors before placing the next tier of nodes. Add the container or page bounds last so they enclose the composed content with breathing room.
5. Enlarge the lane, container, or page when the content exceeds the plan. Do not compress the same information merely to retain an initial canvas size.

Use these as soft starting ranges for new or substantially redesigned content, then increase them for long labels, fan-out, parallel routes, or large shapes:

- 40–60px container padding around meaningful content;
- 48–72px between adjacent node bounds when no route or label must pass between them;
- 80–120px between tiers when the gap carries a labeled route, several branches, or an outcome band;
- 24–32px between parallel routing channels, with additional room for labels.

These ranges are not a fixed grid and do not override a user-supplied composition. Their purpose is to make expansion the default response to density.

## Author routes and labels

- Finish node bounds and routing bands before authoring edges.
- Choose connection sides from the actual relative positions and intended reading order.
- Treat `exitX`/`exitY` and `entryX`/`entryY` as relative connection constraints, not universal rectangular pixel anchors. Resolve the vertex's native Draw.io perimeter before placing the adjacent waypoint.
- Prefer stable axis anchors for common unrotated native shapes: any non-corner boundary point for rectangles and visual containers; top/right/bottom/left cardinal anchors for ellipse/circle, rhombus, and hexagon; and the base-center or apex of a triangle on its orientation axis. An intentional off-axis attachment is allowed only when its shape-specific perimeter projection and adjacent route segment can be proved or officially rendered.
- Add explicit `exitX`, `exitY`, `entryX`, and `entryY` when automatic endpoint choice would crowd a node or merge several edges.
- Add waypoints when a route crosses a region, passes an intermediate node, shares a busy channel, or forms a bidirectional pair.
- Nest waypoint arrays inside the edge's `mxGeometry`. `MISPLACED_WAYPOINT_ARRAY` means Draw.io will ignore the apparent route; repair it before publication:

  ```xml
  <mxGeometry relative="1" as="geometry">
    <Array as="points"><mxPoint x="300" y="120"/></Array>
  </mxGeometry>
  ```

- Use different sides or channels for opposing edges when that improves readability.
- Shorten a long edge label when possible. Put detailed contracts in a nearby note or legend when keeping them on the route would obscure the topology.
- Give every labeled edge in a dense corridor explicit geometry or offset; do not let several labels compete for default midpoints.
- Keep every edge label out of container title bands. Route it through a dedicated corridor with at least 8px of visible clearance from the title band after estimated label bounds are considered.
- Keep non-endpoint edge segments away from node and container borders. Do not use a shape boundary as a routing channel.
- Make the final waypoint approach the target along the explicit target port's outward normal. For several incoming routes to a complex shape, use distinct boundary ports and routing channels separated by at least 24px.
- Distribute a decision's outcomes across available sides or distinct bands rather than stacking every branch and label into the same narrow gap.
- Split a page only when its content cannot remain legible. Do not impose a node-count threshold, fixed grid, palette, waypoint count, or mandatory spacing.
- Prefer topology-aligned placement over a long detour. Put alternative outcomes on different sides of their decision instead of placing one outcome behind an unrelated intermediate node.
- When a crowded route needs more room, enlarge its lane or page instead of compressing the same content.

For each new or substantially redesigned orthogonal edge, evaluate the supported source-port, target-port, and direct/L/Z route candidates together while node positions stay fixed. Choose lexicographically: zero unrelated-node transit; valid source departure and target approach; fewer edge overlaps/crossings; adequate channel clearance; fewer bends; shorter length; then better local symmetry. This is task-local route authoring, not automatic node layout or a persisted IR.

Normalize explicit waypoints before writing XML: remove zero-length and duplicate points, remove collinear middle points, never use a target-boundary point as a routing waypoint, and remove a detour when a lower-bend candidate satisfies all higher-priority constraints. A straight, obstacle-free, port-aligned connection uses no waypoint. Do not reduce bends at the cost of a node transit, invalid endpoint approach, shared channel, or hidden relationship.

Resolve a connection conflict in this order: change the attachment port, add a waypoint, separate the routing channel, move the node, enlarge the container or page, aggregate repeated relationships, add a native line jump, then split the page. Do not shrink text, hide a relationship, stack indistinguishable strokes, or silently delete an edge to make the route fit. Keep same-side explicit ports at least 12px apart and independent parallel routing channels at least 24px apart. These are strict lower bounds, not a fixed grid.

Ports and waypoints reduce routing risk but do not prove the Draw.io renderer's final path. Preserve intentional overlaps and user-specified composition.

## Animate directed semantic flows by default

For newly authored or substantially redesigned content, use Draw.io's native connector style on directed semantic-flow edges after their routes are stable:

```json
{"op":"set-style","cellId":"edge-1","set":{"flowAnimation":"1"},"unset":[]}
```

- Apply `flowAnimation=1` to normal, secondary, data read/write, exception, and retry edges when they represent actual directed movement.
- Omit or unset `flowAnimation` on references, annotations, containment, grouping, and purely structural relationships; do not write `flowAnimation=0`.
- Let the user explicitly request no animation or a narrower animated subset. If rendered QA shows excessive motion, make lower-priority semantic flows static without changing topology.
- During a local edit of an existing diagram, preserve animation on untouched edges. Apply this default only to newly authored/redesigned flow scope, or when the user asks to normalize animation.
- Stabilize endpoints, ports, waypoints, labels, and spacing before enabling animation.
- Do not treat animation as collision avoidance. It changes the stroke presentation, not the route geometry.
- Keep `source`, `target`, and native edge geometry as the editable truth. In the Draw.io editor, attached connectors reroute when nodes move; an exported standalone SVG only animates along its already-exported path.
- Expect motion only in SVG/HTML viewers that permit CSS animation. PNG and PDF are static, and some consumers may rasterize or sanitize SVG.
- Export through Draw.io Desktop or official Draw.io Web. Do not inject custom JavaScript or rewrite the SVG animation manually.

## Interpret `check-layout`

- `collision`: at least one deterministic geometry collision exists. Patch the implicated cells, then recheck.
- `indeterminate`: no conclusion is possible for every route, geometry, or label. Use rendered QA or disclose the limitation.
- `clear`: the configured static checks completed with no collision or unverifiable finding. It is still not evidence of font rendering or overall visual quality.

Use `coverage.totalEdges`, `coverage.checkedEdges`, and `coverage.unverifiableEdges` instead of inferring coverage from an empty collision list. `collisionCount=0` does not prove balanced whitespace or readable density. `UNVERIFIABLE_EDGE_LABEL` means the CLI cannot determine the rendered label bounds. `EDGE_LABEL_WITHOUT_OFFSET` and `MISSING_EXPLICIT_PORT` remain general advisories, but each occurrence in a dense corridor is an unresolved visual risk until it is corrected or covered by readable rendered QA.

`EDGE_AUTOROUTE_VERTEX_TRANSIT_RISK` means an orthogonal edge has no explicit waypoint and at least one simple horizontal-first, vertical-first, or aligned candidate path crosses an unrelated ordinary vertex. The official renderer may choose another route, so this remains a warning rather than a deterministic collision. `candidatePaths` identifies the blocked candidates and `allSimpleCandidatesBlocked` indicates whether every simple candidate was blocked. Prefer an explicit boundary port and waypoint or a separated routing corridor, then confirm the final path in an official render.

For unrotated native rhombus and ellipse shapes, the checker resolves Draw.io's perimeter projection instead of treating the bounding box as a rectangle. It also recognizes cardinal anchors for native hexagons and the orientation-axis anchors of an east-facing triangle. Custom stencils, unsupported perimeter functions, rotation, flips, and direction transforms remain renderer-dependent; never fabricate an exact endpoint for them. `EDGE_SHAPE_PORT_PROJECTION_RISK` is a priority-1 advisory that discloses the raw and projected anchors; it does not reject intentional off-axis attachment. `EDGE_TERMINAL_DOGLEG_RISK` warns when an orthogonal edge's adjacent explicit path point aligns with neither axis of the resolved anchor, so the renderer must add a last-mile bend. `EDGE_REDUNDANT_WAYPOINT` identifies duplicate or collinear explicit points. `EDGE_REDUNDANT_BEND_RISK` is emitted only when a direct or one-bend candidate preserves supported endpoint normals and is provably clear of unrelated ordinary vertices. These route-quality results remain warnings/advisories rather than deterministic collisions, but unresolved warnings in newly authored or redesigned scope block `ready`.

Container bodies are not ordinary business nodes. A legal route entering or leaving an endpoint's ancestor container is ignored. `EDGE_CONTAINER_TRANSIT` means a route crosses an unrelated visual-container body and needs judgment. Only an exact route through an unrelated swimlane title band becomes `EDGE_CONTAINER_HEADER_INTERSECTION`; an approximate route remains a warning.

`TEXT_CLIP_RISK`, `EDGE_LABEL_OVERLAP_RISK`, `EDGE_LABEL_NEAR_VERTEX_RISK`, `EDGE_LABEL_DENSITY_RISK`, and `EDGE_LABEL_PAGE_RISK` use conservative estimated bounds. They prioritize rendered QA and never prove a renderer collision. Page analysis reports content bounds and `occupiedPageTiles`; multi-tile content is advisory unless `--expect-single-page` is set, in which case `SINGLE_PAGE_BOUNDARY_EXCEEDED` keeps the result `indeterminate`.

`EDGE_LABEL_CONTAINER_HEADER_RISK` means an estimated edge-label rectangle enters a swimlane title band or its 4px safety margin. `TARGET_PORT_APPROACH_MISMATCH` means the last explicit waypoint does not approach a non-corner boundary port along its normal. Both are high-priority rendered-QA risks, remain warnings rather than deterministic collisions, and keep the result `indeterminate`. If either remains unresolved and readable rendered inspection is incomplete, report `draft_with_issues`.

Edge-pair findings are grouped by normalized edge IDs so repeated intersections between the same two edges remain one finding with bounded events. `EDGE_PATH_OVERLAP_RISK`, `EDGE_CROSSING_RISK`, `EDGE_CROSSING_WITH_JUMP`, and `EDGE_TOUCH_RISK` are warnings; `EDGE_PARALLEL_CHANNEL_RISK` is advisory. A jump warning means only that the later same-layer connector appears eligible under native order, `curved`, `jumpStyle`, and `noJump` rules. It still requires an official render. Use `coverage.checkedEdgePairs` and `totalEdgePairs` to see how much of the edge-pair space was actually analyzable.

`EDGE_SHARED_PORT_RISK`, `EDGE_PORT_SPACING_RISK`, and `SOURCE_PORT_DEPARTURE_MISMATCH` apply only when axis-aligned native port geometry can be proved. Rotation, flips, direction transforms, endpoint dx/dy offsets, and unsupported perimeters produce `UNVERIFIABLE_PORT_GEOMETRY` instead of a fabricated pixel result. The source check uses the first non-zero segment; the target check uses the last non-zero segment. `EDGE_LABEL_PATH_CLEARANCE_RISK` uses a strict `<6px` rectangle-to-segment distance for explicitly placed labels; default label placement stays renderer-dependent.

`qaPlan` reports total, selected, omitted, and omitted-high-priority region counts. It selects at most eight merged local regions. `QA_PLAN_TRUNCATED` is a warning when priority-2/3 regions were omitted and an advisory when only priority-1 regions were omitted. Do not claim all high-risk local checks passed while `omittedHighPriorityCount` is non-zero; first reduce the risks or split the page.

With `--verbose`, use `result.qaPlan.pages[].reviewTargets`. Every page contains one `fullPage` target plus at most eight merged `riskRegion` targets. Compact output returns counts without per-cell regions.

The default output aggregates repeated route and label findings in `result.summary.warningCounts` and `advisoryCounts`. Use `--verbose` only to locate individual cells, `--only-collisions` when correcting deterministic findings, and a page selector to reduce scope. Suppressed details do not change `status`, coverage, or `renderRequired`.

## Correction budget

Use at most two correction passes by default, counted across layout and rendered QA for the same logical delivery. Each pass applies a focused correction and checks the result. A user-requested high-fidelity reconstruction may use one additional pass; an explicit user request for further iteration overrides the default budget. After the applicable budget, disclose remaining issues and use the appropriate delivery quality rather than claiming they are resolved.

## Run rendered visual QA

1. Prefer a real Desktop render for each required page:

   ```bash
   python3 -I -B <skill-root>/scripts/drawio_file.py render \
     diagram-v001.drawio --page-index 0 --output diagram-v001-page-1.png
   ```

2. If `DRAWIO_DESKTOP_NOT_FOUND` is returned, generate a new companion HTML with `preview`; never replace the source or an existing preview. Open it only when the host browser permits the local file and has network access to the official Viewer.
3. When host Computer Use is available, open the companion HTML, inspect every page in the official Viewer, and capture the rendered evidence. Do not stop at successful HTML generation. A fit-to-page view is only an overview: zoom every dense region until labels are readable and specifically inspect edge labels near node boundaries, bends, and shared routing channels.
4. If neither surface can be inspected, stop visual claims and report `structure_only`. Do not treat renderer failure, blocked navigation, timeout, or an unopened HTML file as a passed check.
5. Capture or inspect the complete diagram at a readable scale, then inspect every `riskRegion` returned by verbose `check-layout`.
6. Check node and text overlap, edge crossings through non-endpoint nodes, label collisions or truncation, unreadable text, shared-route ambiguity, and page overflow. Also check composition: predictable reading order, primary-path dominance, consistent alignment, balanced negative space, container padding, separation of primary and exception outcomes, and whether animated secondary edges create unnecessary visual noise. For explanatory flows, check that object identity, important transformations, and actor ownership are visible rather than encoded only in prose; use the questions in `visual-storytelling.md`. Treat cramped but non-overlapping content as a visual issue. Do not mark a page ready from a screenshot whose scale hides label-level conflicts.
7. Describe each issue by visible label and approximate region. Do not invent a cell ID from pixels.
8. Map the visible label to a unique native cell with `query`. Stop if the match is ambiguous.
9. Apply the smallest geometry, endpoint, waypoint, or `set-label` patch into a new version.
10. Re-render after each correction and follow the [correction budget](#correction-budget).

For multi-page work, also perform the scoped cross-page comparison under [document visual consistency](#document-visual-consistency).

Record visual acceptance with this task-local template; do not create a permanent manifest unless the user asks:

| Version | Page | View | Region/reason | Cell IDs | Result | Corrected in |
|---|---|---|---|---|---|---|
| working-01 | Main | fullPage | composition and page boundary | — | pass/fail | working-02 or — |
| working-01 | Main | riskRegion | `EDGE_LABEL_DENSITY_RISK` | edge-a, edge-b | pass/fail | working-02 or — |

The Python CLI does not implement rendering, open a browser, or call a vision API. `render` only invokes an installed Draw.io Desktop CLI; browser inspection and image understanding remain host-Agent capabilities.

Per-page image delivery is an output format, not evidence that visual QA passed. SVG is optional and exported only when requested. Inspect a readable rendered surface before marking the diagram `ready`; an uninspected SVG only proves that Draw.io Desktop or Web produced a recognizable editable SVG artifact. When a source edge has `flowAnimation=1`, SVG commit/export must report `connectorAnimation.status=preserved`; a missing animation is an export failure, not a permitted static fallback.

## Report delivery quality

- `ready`: internal XML validation passed, deterministic collisions are resolved, every required rendered check passed, and all requested deliverables exist. Default delivery requires per-page PNGs and self-contained offline HTML, not native source or SVG.
- `structure_only`: XML and available static checks passed, but rendered QA was unavailable or incomplete.
- `draft_with_issues`: a deterministic or rendered issue remains after the correction limit.

Do not mark a diagram `ready` when `check-layout` is `indeterminate` unless the unresolved routes and labels were covered by rendered QA. Check multiple themes only when the user requests them or the diagram uses theme-dependent colors, transparency, or backgrounds.
