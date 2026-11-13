# Native authoring and Desktop CLI

Use this reference only when creating, checking, previewing, laying out, opening, or exporting a diagram.

## Author freely

This Skill does not define diagram types, templates, fixed geometry, themes, or allowed style combinations.

- Choose representation before syntax. For new explanatory flows, default to direct native XML with concrete editable objects and visible changes, even when Desktop and Mermaid conversion are available. Mermaid is suitable when it preserves the intended representation, such as formal structural notation or an explicitly minimal-box request; concise topology alone is not a reason to choose it.
- Use native XML for unrestricted Draw.io shapes, stencils, styles, layers, groups, waypoints, tags, metadata, and precise coordinates.
- For a PDF, text, screenshot, or reference image, first read `source-to-diagram.md`; source evidence and visual language outrank generic diagram conventions.
- A user-provided visual language or existing file outranks any example in this reference.
- Do not convert a custom request into a generic flowchart merely because Mermaid is shorter.
- For an explanatory flow, read [visual-storytelling.md](visual-storytelling.md) before creating nodes. Consult its component index, read the relevant starter XML, and reuse/adapt those native parts to show object/action/state changes. When generating a new object, use relevant starter constructions as references instead of skipping the library or reproducing only its surrounding text card. The absence of an exact starter does not justify a text module. Do not flatten these objects to use Mermaid or let a text-first topology sketch become the finished diagram.

## Locate Draw.io Desktop

Check in this order:

```bash
command -v drawio
test -x /Applications/draw.io.app/Contents/MacOS/draw.io
```

Use `drawio` on Linux when it is on `PATH`. On macOS, use `/Applications/draw.io.app/Contents/MacOS/draw.io` when present. This V1 does not define Windows invocation.

If Desktop is missing, create direct XML. A temporary online-only companion can provide the initial official Viewer render. Desktop CLI export/layout remains unavailable. For default PNG delivery, capture each complete diagram from the official Viewer at readable resolution without browser chrome. Use `web-svg-export.md` only for explicitly requested SVGs; do not create a substitute renderer.

Before any conversion, layout, or export command, verify that the output path does not exist. Choose a new path instead of allowing Desktop to replace a file.

## Mermaid to native Draw.io

Write concise Mermaid to a temporary `.mmd`, then run:

```bash
DRAWIO_CMD -x -f xml -o diagram.drawio diagram.mmd
```

Replace `DRAWIO_CMD` with the resolved executable path. Delete the `.mmd` only after a valid `.drawio` was created. Do not export directly from `.mmd`; convert to `.drawio` first.

## Direct XML

Write a native `mxGraphModel` or `mxfile` to a `.drawio` path. Read `drawio-xml.md` for the minimal structure and open primitives. Coordinates, sizes, style values, and shape names come from the task, not from this Skill.

## Layout check and correction

After creating native XML, run:

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py check-layout diagram.drawio --verbose
```

Read `layout-authoring.md` before interpreting the result or correcting a crowded diagram. Correct reported `VERTEX_OVERLAP`, `CHILD_OUTSIDE_PARENT`, `EDGE_VERTEX_INTERSECTION`, and exact `EDGE_CONTAINER_HEADER_INTERSECTION` findings with a small native patch. Treat text, label-density, and page-fit codes as conservative visual risks. Recheck after the patch and follow the [shared correction budget](layout-authoring.md#correction-budget).

This is a geometry linter, not automatic layout or rendered visual QA. It ignores intentional ancestor/descendant containment. `collision` identifies a positive finding. `indeterminate` means route, geometry, or label coverage is incomplete and a real Desktop render or official Viewer render is required for a visual conclusion. Only `clear` means the configured static checks completed without a finding.

Default output is summarized to avoid repeating one warning per renderer-dependent edge. Use `--verbose` for per-cell details and the full-page/risk-region QA plan, `--only-collisions` for deterministic correction, `--expect-single-page` only when the delivery must fit one declared page tile, and `--page-id/--page-name/--page-index` to narrow the result.

`LAYOUT_CHECK_LIMIT` means the page would exceed the lightweight checker's bounded comparison budget. Narrow the page or use rendered QA; do not bypass the limit or claim a clean result.

For business workflows, also run `check-topology` with known starts, accepted terminals, and critical direct edges. Read `topology.md`; connectivity checks and layout checks answer different questions.

## Desktop render for visual QA

Prefer the bundled wrapper so no-clobber and source-revision checks apply:

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py render \
  diagram-v001.drawio --page-index 0 --output diagram-v001-page-1.png
```

All public `--page-index` selectors are zero-based and match `inspect`; prefer `--page-id` for multi-page inputs. The wrapper converts the selected page to Draw.io Desktop's one-based CLI argument internally. The output suffix or explicit `--format` selects PNG, SVG, or PDF. For SVG it also requires safe embedded Draw.io content whose complete selected-page semantics match the source. The command commits only a new file and returns `visualReviewRequired=true`. Inspect the render before declaring visual QA complete. If Desktop rendering fails, try an official Viewer capture. Without an inspected official render, report `structure_only`; a successful inspected Viewer capture satisfies default PNG QA.

## Companion HTML preview

Create a same-version HTML companion for every generated diagram. Pass the final internal `.drawio` as input and place only PNGs and HTML in the default delivery directory. The preview embeds XML and PNG data and must not depend on the internal source path at runtime:


```bash
python3 -I -B <skill-root>/scripts/drawio_file.py preview \
  diagram-v001.drawio --output diagram-v001.html --fallback-png page-01.png
```

The preview reserves the viewport space remaining below the product rail and Viewer toolbar. On initial load, page changes, and viewport resizing, fit the complete diagram within both available width and height and center it, without enlarging small diagrams beyond 100%. Preserve native diagram dimensions and font sizes; overview scaling is a viewing choice, not a layout correction or proof that small text is readable. Users can zoom or pan to inspect details and use the official Fit control to return to the overview. Refit on page identity or container-size changes, not every `graphChanged` event, so manual navigation is not continually reset. The command embeds the source XML in a static shell for the official Draw.io viewer. It does not render or copy the diagram into a second drawing model. Interactive viewing requires network access to `viewer.diagrams.net`. The embedded PNGs display immediately, support actual-size viewing and remain visible if scripts are blocked or initialization fails. Supply one verified PNG per page in source order, from Desktop export or a complete official Viewer capture cropped to diagram content. For a temporary online-only QA shell omit the option. Verify the final HTML with remote requests blocked: every page must remain readable. Recheck online interaction separately.

The shell uses one compact product rail: a restrained file-identity block, an ordered page list, and one primary edit action. Editor handshake details stay hidden until needed and appear below the rail as a transient status surface, never as raw stage text competing with the title. On narrow screens the page list remains available through horizontal scrolling instead of being hidden.

Online previews enable native tooltips. A child without its own tooltip inherits the nearest containing object's tooltip, allowing a composite illustration to carry a detailed explanation without duplicating prose on each decorative part. Store such text in native `object` wrapper `tooltip` attributes. Verify hover on the actual child/caption when promising this behavior. Critical conditions remain visible in the diagram or accompanying notes: embedded PNG fallbacks do not provide hover details.

For multiple pages, the shell displays the page count and ordered page names before the canvas. Page 1 opens initially. Each header page name is a keyboard-accessible button that switches the official Viewer; the active button and `aria-current` also follow navigation through the Viewer toolbar. Tabs share an equal width calculated from available space and total page count, with a 96px minimum, 220px maximum, 4px gaps, and 4px list padding. Long titles use single-line ellipsis; their full names remain button text and hover titles. At the minimum width, the rail scrolls horizontally and reveals the active tab on page changes without scrolling the canvas. Narrow screens place the rail on its own row. Documents are limited to 15 pages. Check the page list before review so later pages are not mistaken for missing content. Do not create one Viewer instance per page or stack full-page canvases; that duplicates the embedded drawing and makes large files unnecessarily heavy.

The preview keeps page buttons disabled until the Viewer is ready. In the online-only shell, script loading failures, initialization exceptions, and a 30-second loading timeout show a visible message and a **Retry preview** button. Retry reloads this read-only HTML to clear any partial Viewer instance; it does not write the native file. A late successful load clears the timeout message. Verify successful switching in both directions, returning to page 1, and keyboard activation.

When maintaining the preview shell, initialize one Viewer through `GraphViewer.createViewerForElement`, call `selectPage` for header navigation, and listen to `graphChanged` for active-state synchronization. Use a container class other than `mxgraph` to avoid automatic duplicate initialization. Keep Viewer loading feedback separate from editor handshake feedback.

Treat the Viewer canvas as a read-only preview. The `Edit a copy` button opens the official `embed.diagrams.net` editor and sends the complete original `mxfile` only after the user clicks it, so every page is loaded into one editable browser session. The bridge accepts messages only from the exact editor origin and popup window.

The preview shows user-facing editor status text and retains diagnostic codes in the status element's `data-stage`, without logging diagram XML. If the editor remains on its loading screen, inspect that attribute in the preview: `EDITOR_INIT_TIMEOUT` means no trusted `init` event arrived, while `EDITOR_LOAD_TIMEOUT` means the native XML was sent but Draw.io did not confirm loading it. Treat these as different failures; do not infer an opener, network, extension, or XML root cause from the loading screen alone.

A static local page cannot safely overwrite its sibling source. Browser Save therefore downloads `<base>-edited.drawio`, leaving the original `.drawio` unchanged. Inspect and validate the download before publishing it as a formal version. Opening the editor sends the diagram to the official Draw.io Web service and requires network access; do not click it when the diagram must remain offline. See the official [embed-mode protocol](https://www.drawio.com/docs/reference/embed-mode/) and [HTML export](https://www.drawio.com/docs/manual/export/export-to-html/) documentation.

## Optional Desktop layout

Only run layout when the user requests it or when authoring XML with intentionally approximate positions:

```bash
DRAWIO_CMD -x -f xml --layout verticalFlow -o laid-out.drawio source.drawio
```

Other Draw.io-supported layout values may be used. The Skill does not prescribe one or implement its own layout engine. Use a new output path unless the user explicitly authorizes a Desktop-managed derivative of a newly generated file.

## Optional SVG delivery (only when requested)

Create `.drawio` first, then use the bundled `render` command so no-clobber, page selection, source revision, and output validation apply. Draw.io Desktop receives `-e`, so the SVG carries embedded diagram data when supported by the Desktop exporter.

For a single-page file:

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py render \
  diagram-v001.drawio --format svg --output diagram-v001.svg
```

For a multi-page file, first inspect its ordered pages, then export each page separately. Prefer stable page IDs; the fallback indices below are zero-based:

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py render \
  diagram-v001.drawio --page-index 0 --format svg --output diagram-v001-page-01.svg
python3 -I -B <skill-root>/scripts/drawio_file.py render \
  diagram-v001.drawio --page-index 1 --format svg --output diagram-v001-page-02.svg
```

Use the deterministic page-number suffix rather than raw page names, which may contain spaces, slashes, duplicate names, or filesystem-sensitive characters. Export every page; never present a page-1-only SVG as the entire multi-page diagram. List the SVG paths in page order at handoff.

SVG is not part of default PNG/HTML delivery and its absence does not affect readiness. If the user explicitly requests SVG, export every requested page. If Desktop is absent, use the loopback session in `web-svg-export.md` to export and safely commit every selected page through `https://embed.diagrams.net`; use the older per-page bridge only for manual recovery. If both official paths fail for a requested SVG, retain the internal `.drawio` and available deliverables, report exactly which requested SVGs are missing, and do not mark that requested delivery `ready`. The Skill does not include a custom SVG renderer.

## Other exports

For an additional PNG or PDF requested by the user, keep the same native-first rule. Direct Desktop equivalents are:

```bash
DRAWIO_CMD -x -f png -e -b 10 -o diagram.drawio.png diagram.drawio
DRAWIO_CMD -x -f pdf -e -b 10 -o diagram.drawio.pdf diagram.drawio
```

Keep the native `.drawio` in an internal working directory. Deliver it alongside exports only when the user explicitly requests native source.

For image reconstruction, export one rendered preview and perform one source comparison when Desktop is available. The companion HTML makes the result easy to open without Desktop, but its existence alone does not prove visual equivalence: the Agent must inspect the rendered result. When no render surface is available, report `structure_only` and disclose incomplete route or label coverage.

## Provenance

The Mermaid/XML selection and Desktop commands are adapted from the Apache-2.0 JGraph Draw.io Codex Skill, pinned for this implementation to commit `14b318b19cc37b159f841227b9d11fbd18ce18ea`. See `NOTICE`.
