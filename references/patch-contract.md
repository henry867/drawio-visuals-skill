# Patch contract v1

Read this reference before creating a patch. Patch JSON is an operation envelope over native Draw.io cells, not a diagram schema.

## Envelope

```json
{
  "version": 1,
  "expectedRevision": "sha256:...",
  "page": {"id": "page-1"},
  "operations": []
}
```

- Allowed top-level keys: `version`, `expectedRevision`, `page`, `operations`.
- `version` must be `1`.
- `expectedRevision` must be the fresh revision returned by this CLI.
- `page` is optional for a bare/single-page document and required for a multi-page document. It must contain exactly one of `id`, `name`, or zero-based `index`.
- Operations execute in array order and commit as one transaction.
- Unknown structural keys are errors. Native XML attributes and style keys remain open.

## Operations

### set-attrs

```json
{"op":"set-attrs","cellId":"node-1","target":"cell","attrs":{"value":"New label","custom":"kept"}}
```

`target` is `cell` or `wrapper`. `wrapper` requires an `<object>` or `<UserObject>`. Attribute names must be safe XML names. Identity attribute `id` cannot be changed.

Attribute values are decoded logical strings. Do not XML-escape them before writing JSON; the CLI performs XML escaping during serialization. Prefer `set-label` over setting `value` or wrapper `label` through this generic operation.

### unset-attrs

```json
{"op":"unset-attrs","cellId":"node-1","target":"cell","attrs":["custom"]}
```

Final structural validation still applies; removing `parent`, `source`, or `target` is allowed only when the resulting native graph remains valid.

### set-style

```json
{"op":"set-style","cellId":"node-1","set":{"fillColor":"#ff0000","customKey":"value"},"unset":["shadow"]}
```

Style names are not enumerated. Existing unmodified tokens are preserved. All occurrences of a changed/unset key are removed, then changed values are appended once. Keys and values must form one native style token and cannot contain `;`.

For newly authored or substantially redesigned content, set native `flowAnimation` on each directed semantic-flow edge after its route is stable:

```json
{"op":"set-style","cellId":"edge-1","set":{"flowAnimation":"1"},"unset":[]}
```

This animates the exported stroke; it does not change routing or resolve collisions. Read `layout-authoring.md` before using it.

Keep reference, annotation, containment, grouping, and purely structural connectors static by omitting the key when authoring XML or unsetting it when animation normalization is in scope:

```json
{"op":"set-style","cellId":"reference-edge","set":{},"unset":["flowAnimation"]}
```

Do not modify unrelated existing animation during a local edit.

### set-label

Decoded rich text:

```json
{"op":"set-label","cellId":"node-1","value":"<b>先公开回写</b><br>status = pending & ready","format":"html"}
```

Literal text:

```json
{"op":"set-label","cellId":"node-2","value":"A & B < C; say \"ready\"","format":"plain"}
```

`value` is always the logical value after JSON decoding. Pass literal `<b>`, `<br>`, `&`, and quotes; never pass `&lt;b&gt;`, `&amp;`, or other XML pre-escaping. The CLI writes a wrapper `label` when the logical cell uses `<object>/<UserObject>`, otherwise it writes the `mxCell` `value`. It also sets the native `html` style to `1` for `html` or `0` for `plain`.

An HTML value containing high-confidence escaped markup returns `DOUBLE_ESCAPED_LABEL` without output. Validation reports existing suspicious values as `POSSIBLE_DOUBLE_ESCAPED_LABEL`; inspect them because literal escaped markup may be intentional.

### set-geometry

Attribute form:

```json
{"op":"set-geometry","cellId":"node-1","set":{"x":"120","y":"80","width":"160"},"unset":[]}
```

Raw native form for offsets, waypoint arrays, or other geometry children:

```json
{"op":"set-geometry","cellId":"edge-1","xml":"<mxGeometry relative=\"1\" as=\"geometry\"><Array as=\"points\"><mxPoint x=\"300\" y=\"120\"/></Array></mxGeometry>"}
```

Use either `xml` or `set`/`unset`, not both.

Waypoint `Array` elements must be nested inside `mxGeometry`, as shown above. A direct `mxCell` child is ignored by Draw.io and fails `validate`/`publish` with `MISPLACED_WAYPOINT_ARRAY`. Applying raw `set-geometry` also removes obsolete direct waypoint arrays from that cell so historical malformed files remain repairable.

### add-cell-xml

```json
{"op":"add-cell-xml","cellId":"node-2","xml":"<mxCell id=\"node-2\" value=\"Free shape\" style=\"shape=custom;\" vertex=\"1\" parent=\"1\"><mxGeometry x=\"20\" y=\"20\" width=\"120\" height=\"60\" as=\"geometry\"/></mxCell>"}
```

The fragment must be exactly one `mxCell`, `<object>`, or `<UserObject>` logical cell, and its logical ID must equal `cellId`.

### delete

```json
{"op":"delete","cellId":"node-2"}
```

Sentinel cells `0` and `1` cannot be deleted. Delete dependent cells explicitly in the same patch; dangling parent/edge references make the entire patch fail.

### replace-cell-xml

```json
{"op":"replace-cell-xml","cellId":"node-1","expectedCellHash":"sha256:...","xml":"<mxCell id=\"node-1\" ...>...</mxCell>"}
```

This is the advanced native escape hatch. `expectedCellHash` must match the current query result and the replacement must retain the logical ID.

## Errors and retry

- `REVISION_CONFLICT`: query the current file, rebuild once, then stop on another conflict.
- `CELL_HASH_CONFLICT`: query the cell again before considering replacement.
- `PAGE_REQUIRED` / `PAGE_NOT_FOUND`: do not guess a page.
- `OUTPUT_EXISTS`: choose a new output path only with user intent.
- `DOUBLE_ESCAPED_LABEL`: rebuild the operation with decoded logical HTML.
- Contract, XML, reference, wrapper, size, or validation errors: stop and report; do not weaken validation or fall back to in-place editing.
