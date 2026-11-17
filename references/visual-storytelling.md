# Explain a process with visible objects

Read for a new or substantially redesigned explanatory workflow, architecture/process explainer, or swimlane diagram. For a narrow source edit, preserve the surrounding language; for reconstruction or prescribed notation, fidelity takes priority. This reference supplies a way to invent suitable graphics, not a fixed theme or mandatory icon set.

When the presentation is unspecified, first use [diagram-selection.md](diagram-selection.md) to choose a form from the reader's question. Use this reference to express that form, rather than choosing a flowchart merely because the component starters resemble process objects. Concrete objects and visible changes are the default for new explanatory flows, including ordinary “draw a flowchart” requests. Do not wait for the user to request illustrations. Meaningful UML/ER symbols remain essential for formal structure; keep their semantics and use visible object/state contents where compatible. The main skill defines task-grounded exceptions; a diagram-type name alone does not waive the default.

## Choose how each concept can be seen

For every main concept or materially different state, choose the first faithful representation below. This is a decision order, not an icon quota or a requirement to eliminate words:

1. **Recognizable object or action:** show the actual thing and its relevant parts, such as empty seats becoming occupied, a ballot entering a tally, or a text sheet becoming an audio waveform.
2. **Visual model of an abstract relationship:** use containment, position, grouping, comparison, counts, sequences, boundaries or before/after changes. Abstract does not automatically mean prose. Visibility can be a private item behind a boundary and public items crossing it; distribution can be grouped tokens; experience dimensions can be short labeled scales.
3. **Precise text alongside the scene:** use short role, verb and state labels immediately when they disambiguate the picture; do not postpone all words until graphics fail. Use longer explanation when a visual model would invent facts, imply an unsupported measurement, or still fail to express the concept accurately. Exact technical names, guards, formulas, errors, source limitations and formal fields remain text. Do not encode arbitrary concepts as puzzles just to reduce word count.

Before geometry, keep a brief task-local note mapping each main concept/state to its visible evidence, required text, and starter to reuse/adapt/reference (or new construction). Group repeated concepts; do not enumerate every decorative cell. For a text fallback, state what a simple visual cannot faithfully explain. This note belongs in working reasoning/QA, not as another prose panel in the delivered diagram.

Ask **what does the drawing communicate beyond the caption?** A device silhouette establishes the endpoint, but does not explain its activity. Browser chrome around paragraphs, a folded corner around prose, and an envelope around arbitrary results do not become semantic illustrations merely by resembling objects. Reuse starter construction techniques, not their default interiors unchanged. A true identity card is appropriate for a role assignment; it is misleading for difficulty or player distribution.

Examples of how to reason about less tangible concepts (use only facts supported by the task):

| Concept | Visible evidence | Text still useful |
|---|---|---|
| Empty seat → claimed seat | Same seat outline, then an occupant and assignment marker | Seat ID, atomic-claim condition and failure reason |
| Night → day → nomination → tally | Moon/sun for phase, seated participants or action-order markers, a pointer to the nominee, ballots and tally marks | Phase names, nomination restrictions, vote threshold; sun/moon alone does not explain actions |
| Experience / difficulty / distribution | Questionnaire choices or labeled dimension scales / ordered challenge steps / role tokens grouped into seats | Dimension names and actual constraints; no invented scores or measured counts |
| Player-visible AI context | Own role and public board enter a context bundle; other players' hidden cards remain outside its boundary | Exact visibility rule; a lock alone does not show which information is excluded |
| Streamed response | Ordered fragments accumulate into a recipient's reply | SSE/API name and persistence limits; do not invent timing |
| Text-to-speech and caching | Text plus voice selection becomes an audio waveform; the same audio object is stored and enters playback controls | Cache key, actual missing-file behavior and errors |
| Broadcast triggers a refetch | Small change signal arrives, receiver requests a separate full record from storage | Protocol/entity names; do not depict the signal as carrying the full private record |

Use illustrative marks only to explain structure, not to invent measurements, guarantees or executable steps. Keep a short note when a reader could mistake illustrative quantities for actual values.

### Check the action, not just the icon

For each key scene, form a plain-language reading: **who does what to which object, and what is different afterward?** Match that reading with the visible participants, direction and before/after state. Preserve the same object's identity and arrangement when showing a state change. Use different objects for a real transformation, not to stand for a status change.

Before accepting a scene, name its most likely alternative reading. A paper pointing to stock might mean receiving goods rather than releasing a hold; a coin pointing to a card might mean an ordinary payment; a bare door may resemble a phone. Repair the causal context: show the same stock before/after, name buyer/seller and reverse the prior payment direction, or show a recipient receiving the parcel. Short labels such as “Hold removed”, “Money back” and “Customer” are part of the explanation, not a failure of pictorial design. Any contextual prior action must be supported by the source and visually distinguished from a new execution step.

Test two things separately: **recognition** (what objects can be seen) and **comprehension** (what the complete scene plus labels says). Covering captions tests the first; restore labels for the second. If a reader can name every icon but cannot tell the action or confuses it with another action, revise the scene rather than adding detail to the icons. Conversely, do not strip useful words just to make a caption-free puzzle. Formal guarantees such as atomicity need explicit text; putting two artifacts inside a cylinder alone cannot establish them.

See the [action-and-state comparison](../examples/readable-scene-comparison.drawio) and its [official render](../docs/images/readable-scene-comparison.png). The earlier comparison files document construction changes, not proof that their intermediate metaphors are sufficiently clear for every audience.

### Check a representative construction before multiplying it

For multi-page work or an unfamiliar visual vocabulary, first compose and officially render a small representative portion: a main object, its meaningful change/handoff, and the hardest abstract concept. This is an internal authoring checkpoint, not an extra user approval or deliverable. On a small familiar single page, the first full-page render can serve this purpose.

Cover names and explanatory prose temporarily to check object recognition. Then restore concise labels and state who acts, what changes and what is transferred; check the likely alternative reading as well as precision. If only “some screen”, “some document” or “some card” remains, the shell explains too little: change its contents or choose a better model before replicating it across pages. If a concept genuinely needs text, keep the text and its local rationale. Do not use a percentage of icons, cell counts, text length or a blanket ban on rectangles as a proxy for semantic quality.

This checkpoint does not replace final inspection of every page and branch. Repeated components can share a construction, but each instance must contain the correct domain information; reuse must not turn distinct stages into identical prose panels.

## Draw simply, but preserve recognition

Aim for the fewest native parts that still identify the object and its relevant action at the delivered size. Simplicity means removing irrelevant detail, not reducing every object to a circle and rectangle. Use the existing component/gallery as a starting point, then tune its silhouette and contents to the subject.

- Give each object a characteristic contour and one or two useful recognition cues: a person needs a head/shoulder or familiar human silhouette; a parcel needs folded faces, a packing seam or shipping label; a clipboard needs its clip and checklist; a phone needs a screen frame and speaker; a message needs an envelope flap or a speech-bubble tail. Choose the cues that survive the actual viewing scale, rather than drawing every possible detail.
- Make the action visible through the relationship between objects. A reviewer inspecting an item is clearer than an isolated person plus a question mark. A magnifier can establish inspection, but does not mean approval; add an outcome only when supported. Keep the original business object identifiable when adding an action cue.
- Preserve familiar symbols when they already identify the entity: a database cylinder, document sheet, queue, decision diamond or UML notation should not become a generic rounded card merely to fit a caption. Add readable contents, action context and concise labels while retaining that recognizable boundary.
- Prefer plain native shapes and verified standard symbols. Use a small consistent family of stroke weights, rounded corners and restrained fills within the document; reserve emphasis for the meaningful object/change. Adapt to an existing style or user request rather than imposing this example's palette or a mandatory icon style.
- Remove decoration that suggests false semantics: conveyor rollers can imply physical transport, a universal checkmark can imply completion, and identity cards cannot represent every abstract parameter. Use actual intake/outlet directions, separate messages, or the appropriate state instead.
- Keep gaps between unrelated parts and sufficient contrast around essential contours. Do not rely on tiny text, faint strokes, subtle color changes or overlapping silhouettes to make an object recognizable. Avoid pictograms that only become understandable after zooming far beyond the normal reading scale.
- In the representative render, inspect both the normal full-page view and a readable detail view. Temporarily cover captions: can the object category and action be identified? Restore captions to confirm exact meaning. If recognition fails, improve silhouette, cue placement or scale; do not automatically add more parts or longer prose.

See the [before/after component comparison](../examples/component-comparison.drawio) and [official render](../docs/images/component-comparison.png) for concrete construction changes. These illustrate economical recognition, not a fixed template or proof that every recipient will interpret an icon identically.

## Establish what actually moves and who acts

Before choosing shapes, identify the user-visible start, the actors, the thing being transferred or transformed, the important conditions, and the observable end. Use the source or the user's stated facts; mark gaps rather than inventing infrastructure.

- Start at the requested entry point: for example, a user submitting a form, an operator receiving a parcel, or a device capturing a measurement. Do not silently start halfway through at a queue consumer.
- Distinguish the initiator, API handler, event publisher, consumer, and storage owner. Triggering resource creation does not by itself prove which service publishes the event. If responsibilities are collapsed for readability, name the scope and preserve the actual handoff in a short note or tooltip.
- Separate control from artifacts. A worker may save a file **and** make a callback; the storage icon should not become the callback's sender. Similarly, drawing a payment record does not imply the database sends money.
- A successful HTTP response, queued task, completed job, and user notification are different milestones. Show the relevant one; do not use a green checkmark to merge them.

## Invent the visual from its meaning

Use this reasoning in the task, without introducing a persisted scene schema:

1. **Object:** What could the reader recognize? A file, request envelope, parcel, person, calendar slot, machine, account, record, or collection.
2. **Structure:** Which visible parts distinguish it? A folded corner, payload strip, queue slots, rack rows, column grid, document stack, or two account balances.
3. **Action:** What happens to it? Create, enqueue, inspect, split, merge, encode, approve, ship, or store. Put the short verb on the actual action/connector.
4. **Change:** What is different afterward? One document becomes several fragments; fragments become numeric vectors; an unchecked checklist gains a mark; a parcel moves into a delivery bin.
5. **Owner:** Who performs that action, and which boundary is crossed? Position the action in that actor's lane; keep payloads distinct from the machines handling them.

Prefer an existing native symbol when it already explains the concept. Otherwise compose a recognizable silhouette from editable native shapes, then add only the parts that convey structure, state, or action. Verify unfamiliar stencil names in the official renderer; do not guess a library-qualified name and assume it rendered.

For an unfamiliar object, sketch the few characteristic parts and its before/after state. Examples beyond the bundled starters:

- Booking: calendar cells + a selected slot → a reserved slot + confirmation ticket.
- Fulfillment: order slip → packed parcel → sorting bins → delivered parcel.
- Reconciliation: two record columns → matched pairs + a clearly separate unmatched pile.
- Approval: a person + a checklist → approved document or a returned document with a correction mark.

For domain-specific example objects, express outcomes on the affected artifact: an order record is rejected, reserved stock becomes available, funds return to the payment instrument, and a parcel reaches the recipient. A phone or generic check/cross is appropriate for a notification/status display, not a substitute for every business outcome. A shared storage boundary can contain distinct order and event artifacts while an exact caption retains the atomicity guarantee. Reuse the same object identity across workflow and lifecycle views. Prefer native directional shapes to font-dependent arrow glyphs when direction is essential. See the [example-object comparison](../examples/example-object-comparison.drawio) and [official render](../docs/images/example-object-comparison.png).

These are suggestions, not evidence of real behavior or permission to add steps.

## Replace step labels with visible evidence

Choose the object and transformation first, not a fancy outline for the step name. These contrasts illustrate decisions rather than a required palette or component catalog:

| Text-only fallback | Representation that carries meaning |
|---|---|
| Rectangle “Upload PDF” | Browser with a selected folded PDF and transfer arrow to a file-bearing object store |
| Rectangle “Create task” | Request/order record producing a distinct event envelope with a short payload strip |
| Rectangle “Queue” | Intake, separate task cards, and outlet connected to the real consumer; counts explicitly illustrative |
| Rectangle “Parse / split” | A document entering an extractor and emerging as readable text/image parts or separate chunks |
| Rectangle “Approve” | Reviewer inspecting a checklist/document, then an actual marked or returned item |
| Rectangle “Retry” | Failed task returning through a timer/attempt marker to its worker, with the exhaustion path still visible |

An unchanged server icon with a different caption explains ownership but not the transformation. Show its input/output artifact or meaningful internal contents. Draw controls with their standard symbols and retain event names, guards and consequential conditions as text; illustrations do not replace precise semantics.

## Choose a representation that carries information

| Meaning | Useful visible construction | Avoid implying |
|---|---|---|
| User interaction | Browser/device + selected item + upload/submit affordance | That the client performs backend work |
| File or business document | Folded sheet + format/type mark + a few content lines | That a whole document is sent when only its ID/URL moves |
| Message/task | Envelope or payload card + creation mark + short event name | That its triggering service necessarily publishes it directly |
| Buffer/queue | Intake, several separate message cards, outlet, consumer arrow | Measured backlog, FIFO, parallelism, or retry guarantees without evidence |
| Worker/service | Processor/rack/machine accepting an object and emitting a result | That every service is an AI agent |
| Stored data | Container/cylinder + recognizable contents or data type | That storing data completes downstream processing |
| Split/batch | One object changing into visibly separate pieces | Actual counts from illustrative pieces |
| Structured records | Headers and a small row/column sample | A schema or field set unsupported by the source |
| Embedding/encoding | Text fragments becoming short numeric rows or bit patterns | Real measured values, dimensions, or a specific model |
| Human review | Person + inspected item + decision/return action | Automatic approval or an unverified human step |
| Condition | Recognizable gate/diamond + labeled exits | An unlabeled success path or omitted relevant failure |
| Completion/notification | State mark on the affected object or recipient device | Completion at the earlier enqueue/acknowledgment stage |

Keep technical names where they identify the real entity. Put a short name beside the illustration and a concise action on the connector. Move implementation details to notes or tooltips; keep consequential conditions and uncertainties visible even in the static PNG. Color and animation support the explanation; they should not be the only way to distinguish outcomes.

## Make visual meaning a default acceptance condition

For every new explanatory flow, choose the graphic representation before writing node prose; the user need not request concrete or pictorial expression. For each main object or materially different state, decide which visible parts show its identity and which parts change. This can be a brief task-local note; do not introduce a stored schema or force the same illustration on every domain.

For example, an order lifecycle can retain state boundaries and event/guard/action arrows while showing an order slip beside a reserved stock tray, a pending payment card, an open parcel being packed, that parcel aboard a truck, and a delivered parcel at a doorway. Keep the order identity consistent. A clock becoming a checkmark can distinguish a pending refund from a confirmed refund. These drawings describe the state of the order, not extra execution steps.

A shared rounded state boundary is valid; an empty boundary whose only changing content is a state name is insufficient for a new explanatory lifecycle unless the task requires that formal-only representation. A server rack copied for every action or a small unrelated icon beside a paragraph also fails: the graphic must encode a relevant difference. Do not decorate conditions, labels, or formal notation that already carry their necessary meaning.

During official-renderer QA, inspect **every page** for both recognition and comprehension. Briefly cover captions to check the objects, then restore short labels and check actions, participants, changes and likely misreadings. Inspect failures and recovery as well as the happy path. Correct missing visual meaning before marking the result ready. Automated structure, topology, and collision checks cannot judge this requirement; report the visual evidence rather than treating a passing test as proof.

## Start from existing native components

Before inventing graphics for a new explanatory flow, consult this index and open the relevant starter XML. Choose among direct reuse, adaptation/combination, and reference-based generation of a new native object according to the task. For generation, inspect how the nearest starter encodes its recognizable silhouette, contents, state, parent/child structure and ports, then transfer the relevant construction ideas. The sample palette, exact dimensions and captions are not mandatory. For a document pipeline, browser/document/storage/message/queue/worker/chunks/vectors are likely starting points; read only the assets needed. If the library lacks a suitable object, build a new one from native parts rather than forcing a misleading metaphor or falling back to a text box.

Use the [rendered component gallery](../docs/images/components-en.png) to recognize available constructions, then inspect the relevant native source. For richer combinations beyond the starters, consult the [commerce example](../examples/ecommerce-order.drawio) and its [rendered workflow](../docs/images/commerce-checkout.png) when useful; borrow construction patterns, not the example's business facts. User-provided libraries and existing in-scope diagrams can also supply reusable parts. Verify any additional built-in stencil in the official renderer before relying on it.

In the task-local concept note, identify the actual component/example consulted and what will be retained or changed. For example, reuse browser chrome but replace its sample prose with a seat-selection scene; combine message and document parts for a context bundle; reference vectors' repeated rows for incremental reply fragments without calling those fragments embeddings. If no source fits, create a new native construction and explain its visual meaning. Merely listing component names or copying their caption panels is not evidence of useful reuse.

The bundled files below contain only native Draw.io cells. These 12 starters are a seed library, not a capability limit or an exhaustive list of objects. An agent can combine them, modify their parts, or author a new native object using the method above. Each is a standalone single-page document with a semantic root group named `component`. Inspect/read just the files relevant to the task. When adding or maintaining these bundled components, all captions, fields, illustrative text values, states, page names and tooltips must be English; numbers, formulas and symbols may remain as such. When generating a diagram, replace sample captions, fields and tooltips with the task's requested/source language; the starter language does not override the user. Their sample colors, language, dimensions, and captions are replaceable; they are neither branding nor a complete diagram template.

| Starter | Asset | Adaptation examples |
|---|---|---|
| Browser interaction | [browser.drawio](../assets/components/browser.drawio) | Upload, form submission, dashboard action |
| Document | [document.drawio](../assets/components/document.drawio) | PDF, invoice, contract, report |
| Message | [message.drawio](../assets/components/message.drawio) | Event, command, queued task, mail |
| Queue | [queue.drawio](../assets/components/queue.drawio) | Buffer, inbox, work backlog; set real intake/outlet directions |
| Worker | [worker.drawio](../assets/components/worker.drawio) | Consumer, parser, processing service |
| Storage | [storage.drawio](../assets/components/storage.drawio) | Object store, database, archive |
| Pieces/collection | [chunks.drawio](../assets/components/chunks.drawio) | Chunks, batch items, split documents |
| Record table | [table.drawio](../assets/components/table.drawio) | Extracted fields, inventory, reconciliation |
| Encoded values | [vectors.drawio](../assets/components/vectors.drawio) | Embeddings, feature rows, encoded representation |
| Human review | [review.drawio](../assets/components/review.drawio) | Approval, inspection, correction |
| Decision | [decision.drawio](../assets/components/decision.drawio) | Condition gate; attach actual labeled exits |
| Recipient result | [notification.drawio](../assets/components/notification.drawio) | Notification, confirmation, status display |

Match the starter's contents to the actual subject. A storage cylinder may show record rows, but object storage should show the relevant files/objects and its exact name; do not merge database and object-store identity into a generic “DB / S3” label. The chunks starter shows a split transformation: for an already-split collection, reuse only its output pieces. Numeric vectors and tables legitimately need values/fields; use aligned dimensions and separators rather than replacing them with decorative icons. A rack is a service/processing symbol, not proof of physical servers or replica counts. See the [storage, splitting and vectors comparison](../examples/data-component-comparison.drawio) and [official render](../docs/images/data-component-comparison.png).

To reuse a starter:

1. Read the native XML and select `component` **and every descendant by parent links**, including wrapped cells. Do not copy the entire page as a picture.
2. Create a collision-free ID mapping for **all** selected cells, not only IDs beginning with the root's name. Rewrite wrapper/cell IDs, internal parents, and any internal edge endpoints. Attach the semantic root to the destination layer/lane.
3. Preserve child-relative geometry. Move the root, then resize/recompose to the task's actual labels. Scaling a group box alone does not scale its native children or font sizes.
4. Connect the flow to the semantic root or its deliberately exposed ports, not to a decorative flap, status dot, or text line. Parent a progress fill inside its track and icon details inside their enclosing shapes so intended containment remains explicit.
5. Change labels, contents, state, directions, and notes. Remove sample parts that imply behavior the source does not support. Use `patch` operations when inserting into an existing diagram; use direct XML for a new composition, following the main skill's scope rules.

Author missing objects with the same object/structure/action/change reasoning. Do not force a domain concept into the nearest starter if the metaphor distorts it.

## Compose the flow, not an illustrated list

Show the identity of the thing flowing through meaningful transitions. A file → text + images → fragments → vectors is more explanatory than four boxes named “parse”, “process”, “split”, and “store”. An unchanged machine with a new label does not show a transformation.

Use messages as transferred objects, queues as buffers, workers as actors, and storage as destinations/read sources. Draw publish and consume as distinct relationships when that distinction matters. Show relevant branches beside the main path; do not turn parallel consumers into a serial assembly line.

For swimlanes:

- **Horizontal lanes:** roles are rows; progress normally moves left to right.
- **Vertical lanes:** roles are columns; progress normally moves top to bottom.
- Preserve upright graphics when changing orientation; do not rotate the whole drawing or merely replace “vertical” with “horizontal” in the title.
- Put actions in their verified owner lanes and connect across boundaries. Separate user action, API execution, queue transport, processing, and storage where the source requires it; the exact number of lanes is task-specific.
- Share a time/phase area for closely related work rather than giving every field, message, and helper its own distant column. Reserve readable corridors for return callbacks and data reads. Do not shrink glyphs to retain an arbitrary page width.

## Check that the graphics explain something

Apply these questions during the main skill's official-renderer QA, not as an extra fixed review loop:

- With long prose covered, can the reader still identify the main objects, handoffs, and important before/after changes?
- Do the graphics distinguish a request from a worker, a queue from a database, and a stored artifact from a callback sender?
- Does the starting actor and each action's lane agree with the source/user facts? Is an unverified publisher or deployment claim labeled rather than silently assigned?
- Are message cards attached to real enqueue/dequeue flows, with illustrative quantities clearly distinguished from metrics?
- If every illustration could be swapped for the same rectangle without losing information, which key transition should be drawn more concretely? Improve that transition rather than adding decorative icons everywhere.
- Are conditions, relevant exceptions, and completion boundaries understandable in the PNG? Test promised hover details on a child of a grouped object; do not claim offline hover support from an embedded PNG.
- Are all parts still editable native objects, with labels legible at useful zoom and the required paths passing topology checks?

Keep standard symbols when they encode structure or control: class/ER compartments, lifelines, state boundaries, conditions, forks and joins are not decorative boxes. Preserve explicit formal-only requests, source reconstruction, and scoped local edits. Do not extend these exceptions to ordinary explanatory workflows or treat “simple”, “standard flowchart”, or unspecified style as permission to return a text-module chain.
