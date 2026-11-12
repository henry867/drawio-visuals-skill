# Open Draw.io XML reference

Use this reference only when authoring direct XML or preparing a native cell fragment. It describes primitives, not templates.

## Minimal document

A single-page file may be a bare model:

```xml
<mxGraphModel>
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
  </root>
</mxGraphModel>
```

An `mxfile` contains one or more `<diagram id="..." name="...">` pages whose content is a plain `mxGraphModel` or canonical Draw.io compressed payload.

## Native cells

- A vertex is an `mxCell` with `vertex="1"` and an `mxGeometry` child.
- An edge is an `mxCell` with `edge="1"`, `source`/`target` as needed, and an `mxGeometry relative="1"` child.
- Layers, groups, labels, images, swimlanes, containers, and specialized shapes remain ordinary cells and parent relationships.
- Tags, placeholders, labels, and arbitrary metadata may use a canonical `<object id="...">` wrapper containing exactly one direct `mxCell`.
- Existing legacy `<UserObject>` wrappers may be preserved.

Every logical cell ID must be unique within its page. For a wrapper, the outer `id` is authoritative; an inner `mxCell` ID must be absent or identical.

## Unrestricted styling

The `style` attribute is a semicolon-delimited native Draw.io string. This Skill does not enumerate keys or values. Preserve unknown tokens. Examples may demonstrate syntax but never establish a required palette, node size, shape, or routing policy.

Common native concepts include:

- `shape=<stencil-or-shape-name>`
- `rounded`, `whiteSpace`, `html`
- `fillColor`, `strokeColor`, `fontColor`
- `edgeStyle`, `curved`, `orthogonalLoop`
- `image`, `imageAspect`, `verticalLabelPosition`

Use any valid Draw.io style needed by the task, including library-qualified stencil names.

## Geometry

`mxGeometry` attributes and children are native and open. Use explicit `x`, `y`, `width`, `height`, relative geometry, offsets, and waypoint arrays when required. The Skill does not snap values to a grid or remove waypoints.

Before delivery, use `check-layout` to catch obvious positive-area overlaps and line paths through non-endpoint vertices. Read `layout-authoring.md` for flexible endpoint, waypoint, label, and rendered-QA guidance. Do not add waypoints or spacing rules mechanically: preserve intentional overlaps, grouping, and task-specific composition. Draw.io-computed routes and labels remain renderer-dependent when the checker returns `indeterminate`.

## XML safety

- Encode as UTF-8.
- Do not include a DOCTYPE, entity declaration, or XML comment.
- Escape `&`, `<`, `>`, and quotes in attribute values.
- Use unique IDs and valid `parent`, `source`, and `target` references.
- Do not add a fixed theme or normalize unrelated cells.

The bundled CLI semantically preserves supported unknown attributes/elements but does not promise byte-for-byte output identity.

## Provenance

Format facts are adapted from JGraph's Apache-2.0 Draw.io XML guidance at commit `14b318b19cc37b159f841227b9d11fbd18ce18ea`. Prescriptive fixed-grid/theme material is intentionally excluded.
