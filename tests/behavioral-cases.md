# Behavioral regression cases

Run these when changing authoring defaults or representation guidance. Unit tests validate file tooling; they do not show that an agent will choose meaningful graphics. Give each request, the skill path, and an empty output directory to a fresh agent without the rubric or a proposed fix. Request native source only to isolate authoring, then inspect an official Draw.io render of every resulting page. Keep evaluation artifacts outside the repository unless explicitly adding a public example.

## Requests

1. Draw an e-commerce returns/refund workflow: the customer submits a return, the order service checks the return window and rejects expired requests, an accepted request produces a shipping label, the customer sends the parcel, the warehouse receives and inspects it, rejected items go to human review, accepted items trigger payment-platform refund, successful refunds notify the customer, transient failures enter a task queue for at most three retries, and exhausted retries go to human review.
2. Create two pages: a document-search ingestion workflow (browser PDF upload to object storage, file reference to resource API, resource creation and event publication, queue, parsing worker, text and image extraction, text chunks, embedding, index, bounded retry and human escalation); and a strict UML class diagram of Document(id, title), Chunk(id, text), Embedding(id, vector), with Document containing 1..* Chunks and a Chunk having 0..1 Embeddings.
3. Reconstruct a supplied text-box flowchart faithfully, or change one named edge label in an existing file. Supply the actual reference/file and precise requested scope; do not request a redesign.
4. Draw a simple ticket-processing workflow: a user submits a problem from a webpage, the service creates a ticket message and enqueues it, a background processor consumes it, saves the result to a database and notifies the user after saving, while processing failures go to a human.

These prompts deliberately omit instructions to use icons or be pictorial. Case 2 also checks that a default does not erase a formal diagram's semantics; case 3 checks preservation of existing user content. These are diagnostic cases, not an exhaustive guarantee or a fixed diagram template.

## Review the output

For new explanatory pages, cover captions in the official render and identify the main objects, handoffs and changes. In case 1 distinguish the application/return label, transported parcel, inspection, pending/completed refund, task queue and human escalation. In case 2 distinguish a PDF, its storage/reference, creation event, queued work, extracted parts, chunks and encoded/indexed result. A row of labeled rounded rectangles, repeated generic machines, emoji, or an unrelated small icon beside a paragraph fails. A standard decision or fork is legitimate; not every control needs illustration.

Check that the agent actually consulted the component index and opened relevant starter XML before generating objects; review whether direct reuse, adaptation/combination, or reference-based generation fits the domain rather than requiring a fixed object count. Inspect native source for genuine editable parts and semantic endpoints, then verify the required paths, rejection/escalation branches and retry bound. Render at readable scale to check labels, edges and geometry. For the class view, verify named compartments, attributes, associations and cardinalities; do not demand decorative objects inside every class. For reconstruction/local edits, compare source content and ensure unrelated parts did not change.

Record what was actually observed, including an unsuccessful baseline or remaining issue. Distinguish representation acceptance, structural/topology checks and rendered layout acceptance. Do not claim a statistical success rate or future reliability from a small number of runs, and do not replace this review with assertions that instruction wording exists.
