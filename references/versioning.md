# Pages and immutable versions

Use this reference for page CRUD, publishing, or lightweight history. Every write requires a fresh revision from the bundled CLI, writes one new file, and leaves its source unchanged.

## Page CRUD

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py page add INPUT \
  --name NAME [--id PAGE_ID] [--model-file MODEL_XML] \
  --expected-revision REVISION --output OUTPUT

python3 -I -B <skill-root>/scripts/drawio_file.py page rename INPUT \
  (--page-id ID | --page-name NAME | --page-index INDEX) \
  --name NEW_NAME --expected-revision REVISION --output OUTPUT

python3 -I -B <skill-root>/scripts/drawio_file.py page delete INPUT \
  (--page-id ID | --page-name NAME | --page-index INDEX) \
  --expected-revision REVISION --output OUTPUT
```

- `add` appends a blank page unless `--model-file` supplies one UTF-8 bare `mxGraphModel`. A full `mxfile` is invalid.
- Omit `--id` to generate a unique `page-` ID. Prefer the returned ID for later operations.
- Adding to or renaming a bare model converts the new output to `mxfile`; its original page defaults to `Page 1`.
- Page names may repeat. A name selector must resolve uniquely; otherwise use ID or index.
- Deleting the last page is forbidden.
- Execute one page operation per command. Page reorder, duplicate, and cross-file move are unsupported.

## Immutable history

Treat three-digit sibling native versions as internal editable snapshots by default. Place them in an internal working directory, not the default image/HTML delivery directory. They become user-visible only when native source is explicitly requested:

```text
diagram-v001.drawio
diagram-v002.drawio
diagram-v003.drawio
```

An existing unversioned `diagram.drawio` remains the origin. Never rename or mutate it merely to start history.

By default, one user-approved logical change produces at most one final internal sibling `<base>-vNNN.drawio`. Multiple patch/page/QA writes within that change belong in an Agent-owned temporary directory as `working-01.drawio`, `working-02.drawio`, and so on. They are not formal versions and must not be placed beside the version series.

A single atomic edit that needs no later correction may write directly to the next internal native version. For multi-page edits, topology/layout correction, or rendered feedback, finish the complete working chain first. Optionally publish one internal snapshot, or a native deliverable if explicitly requested:

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py inspect WORKING
python3 -I -B <skill-root>/scripts/drawio_file.py publish WORKING \
  --expected-revision REVISION --output FORMAL_OUTPUT
```

Before choosing a sibling output, run `versions` on the current formal file and normally select the next unused number. A user-requested non-version output name remains valid.

`publish` validates the working Draw.io file and copies it byte-for-byte to any user-chosen, nonexistent output. It does not infer a version number, inspect a baseline, require a specific working directory/name, decide whether QA passed, or delete temporary files. If `OUTPUT_EXISTS` occurs, rescan the formal series and retry once with the intended unused path.

Generate delivery HTML and per-page PNGs from the same final checked internal snapshot; publication is not required for image/HTML delivery. Retain that snapshot internally for later edits and remove only disposable task-created QA files. Never delete existing sibling versions as automatic cleanup.

## List and restore

```bash
python3 -I -B <skill-root>/scripts/drawio_file.py versions INPUT
python3 -I -B <skill-root>/scripts/drawio_file.py inspect OLD_VERSION
python3 -I -B <skill-root>/scripts/drawio_file.py restore OLD_VERSION \
  --expected-revision REVISION --output NEW_HIGHER_VERSION
```

`versions` recognizes only same-directory, non-symlink `<base>-vNNN.drawio` files and returns at most 200 entries. `restore` copies the selected old version byte-for-byte into a new output after validation and revision checks.

No manifest, database, thumbnail, tag, or cleanup process exists. Moving or renaming a file removes it from automatic series discovery but does not affect Draw.io validity.

On `REVISION_CONFLICT`, inspect the source again and retry once. On `OUTPUT_EXISTS`, rescan the series and choose the next unused number; never overwrite.
