# Explain a process with visible objects

Read for a new or substantially redesigned explanatory workflow, architecture/process explainer, or swimlane diagram. For a narrow source edit, preserve the surrounding language; for reconstruction or prescribed notation, fidelity takes priority. This reference supplies a way to invent suitable graphics, not a fixed theme or mandatory icon set.

When the presentation is unspecified, first use [diagram-selection.md](diagram-selection.md) to choose a form from the reader's question. Use this reference to express that form, rather than choosing a flowchart merely because the component starters resemble process objects. Meaningful standard UML/ER symbols may already be the right representation. This is not a waiver of an explicit request for concrete graphics: preserve that request across pages and diagram-type changes, adding meaningful editable contents inside formal boundaries where compatible.

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

These are suggestions, not evidence of real behavior or permission to add steps.

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

## Make pictorial intent an acceptance condition

When the user requests concrete or pictorial expression, choose the graphic representation before writing node prose. For each main object or materially different state, decide which visible parts show its identity and which parts change. This can be a brief task-local note; do not introduce a stored schema or force the same illustration on every domain.

For example, an order lifecycle can retain state boundaries and event/guard/action arrows while showing an order slip beside a reserved stock tray, a pending payment card, an open parcel being packed, that parcel aboard a truck, and a delivered parcel at a doorway. Keep the order identity consistent. A clock becoming a checkmark can distinguish a pending refund from a confirmed refund. These drawings describe the state of the order, not extra execution steps.

A shared rounded state boundary is valid; an empty boundary whose only changing content is a state name is insufficient for a requested pictorial lifecycle. A server rack copied for every action or a small unrelated icon beside a paragraph also fails: the graphic must encode a relevant difference. Do not decorate conditions, labels, or formal notation that already carry their necessary meaning.

During official-renderer QA, inspect **every page** with node captions mentally covered. Can the reader distinguish the main objects and meaningful changes, even if exact events or guards still need labels? Inspect failures and recovery as well as the happy path. Correct missing visual meaning before marking the result ready. Automated structure, topology, and collision checks cannot judge this requirement; report the visual evidence rather than treating a passing test as proof.

## Reuse editable starters selectively

The optional files below contain only native Draw.io cells. These 12 starters are a seed library, not a capability limit or an exhaustive list of objects. An agent can combine them, modify their parts, or author a new native object using the method above. Each is a standalone single-page document with a semantic root group named `component`. Inspect/read just the files relevant to the task. Their sample colors, language, dimensions, and captions are replaceable; they are neither branding nor a complete diagram template.

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

For ordinary formal flowcharts, state machines, technical schemas, and simple sequences, standard shapes may communicate well without extra illustration. Preserve that clarity when no pictorial treatment is requested. When it is requested, apply the acceptance condition above without obscuring formal semantics; do not use this exception to revert a page to generic text modules.
