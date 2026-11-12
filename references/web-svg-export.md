# Official Draw.io Web SVG fallback

Use this reference only when Draw.io Desktop is unavailable and editable SVG delivery is required. This is an explicit network fallback, not a custom renderer or a visual-QA pass.

## Privacy and scope

Both workflows send exactly one selected page at a time to `https://embed.diagrams.net`. A multi-page source is projected into sequential temporary single-page `mxfile` payloads; the complete file is never sent through the SVG export path. Do not use this fallback when the user forbids remote processing.

## Preferred loopback session

Run one loopback-only session from the final native version:

```bash
python3 -I -B <skill-root>/scripts/web_svg_session.py \
  diagram-v001.drawio --output-dir OUTPUT_DIRECTORY --timeout 300
```

The command binds an ephemeral port on `127.0.0.1` and prints `WEB_SVG_SESSION_URL=...` to stderr. Open that exact one-time URL with the host browser. The page loads each selected projection into the official Draw.io iframe, requests editable `xmlsvg`, posts the result back to the loopback session, validates it, and commits it directly to the output directory. It does not use or poll the browser Downloads directory.

By default every page is processed in source order. To retry one failed page, add exactly one zero-based `--page-index`, stable `--page-id`, or `--page-name`. Single-page output uses `<base>.svg`; multi-page output uses `<base>-page-01.svg`, `-page-02.svg`, and so on.

The server accepts only its random session token, the exact loopback Origin, configured payload sizes, and one submission for each selected page. It shuts down after success, validation failure, or timeout. Each page uses the source revision captured at session start; a source change stops later commits. Successfully committed pages remain no-clobber outputs and can be retained while failed pages are retried individually.

The Host Agent opens the URL and inspects the result. The helper does not launch or automate a browser, take screenshots, call a vision model, or render SVG itself.

## Manual recovery

If the loopback session cannot be used, get a fresh revision and create a per-page bridge. A multi-page file requires a selector:

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py web-svg-bridge \
  diagram-v001.drawio --page-id PAGE_ID --output /tmp/diagram-page-01-svg.html
```

Open the new bridge HTML. It checks both `event.origin` and the iframe window, sends the selected projection to official Draw.io Web, requests `xmlsvg`, and enables `Download editable SVG` only after an export response. Commit the download with the same fresh revision and selector:

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py commit-web-svg \
  diagram-v001.drawio DOWNLOADED.svg --page-id PAGE_ID \
  --expected-revision sha256:... --output diagram-v001-page-01.svg
```

Repeat for every missing page. Never present one page export as the entire multi-page file.

## Validation contract

Both workflows require an editable Draw.io `content` attribute, parse its embedded native XML, and verify page identity, complete cell set, labels, styles, geometry, references, wrappers, and unknown native content against the selected source page. They accept only verified official-editor representation normalization: viewport `dx`/`dy`, insertion of known default `mxGraphModel` editor attributes, omitted zero `x`/`y` on relative geometry, and physical XML relocation that preserves order within each logical parent.

If a selected source edge uses native `flowAnimation=1`, validation also requires Draw.io's exported CSS keyframes and an animation declaration under that edge's `data-cell-id`; otherwise it returns `WEB_SVG_ANIMATION_MISSING` without that output. Validation rejects stale revisions, active elements or attributes, dangerous URL/CSS schemes, unsupported doctypes, semantic page changes, symlink outputs, and existing outputs. It never modifies the source.

## Quality boundary

A committed SVG remains editable because Draw.io XML is embedded in it. Export success does not prove that labels, routes, shapes, or animation density are visually correct. Inspect the full-page view and every high-risk local region from `check-layout --verbose`; otherwise report `structure_only`. If the official iframe is unreachable, its response is malformed, or validation fails, fail closed and list the missing page SVGs.
