# Choose the diagram by the question

Read when the user has not specified a diagram type, or asks to substantially change the presentation. The available Draw.io shapes, component starters, Mermaid support, and the previous task's diagram type do not decide which form is appropriate.

## Preserve explicit intent first

- Follow a requested type, notation, and orientation: a sequence diagram stays a sequence diagram; a horizontal swimlane has roles in rows and progress along the horizontal axis.
- Preserve a supplied reference and the scope of local edits. Do not replace an existing class diagram with an illustrated workflow because its nodes contain text.
- If a different type would materially change the requested deliverable, explain the tradeoff and obtain agreement before substituting it. Within the requested type, make ordinary composition choices autonomously.
- If the type is open, infer the principal reader question from the content and intended audience, choose a suitable form, and continue. State the reason briefly when helpful; do not turn ordinary diagram creation into a questionnaire.

## Match the principal question to a form

This is a decision aid, not an exhaustive or mandatory taxonomy. UML and non-UML representations are both available.

| What the reader needs to understand | Often suitable | What makes it useful |
|---|---|---|
| What happens next, under which conditions? | Flowchart; UML activity diagram | Actions, branches, parallel work and joins |
| Who performs each step, and where does work cross a boundary? | Swimlane flowchart; UML activity partitions | Responsibilities and handoffs as well as progression |
| Who calls whom, in what order, with which response/timeout? | UML sequence diagram | Lifelines, ordered messages, replies, alternatives and loops |
| Which interactions matter more than precise temporal order? | UML communication diagram | Interaction structure with numbered messages |
| Which states can this entity occupy, and what triggers a transition? | UML state machine; lifecycle/state-transition diagram | States, event/guard/action transitions, initial/final states |
| Which services/modules exist and what depends on what? | UML component diagram; C4 context/container/component view; architecture diagram | Structural boundaries, interfaces and dependencies |
| Where do runtime instances execute and communicate? | UML deployment diagram; infrastructure/network topology | Nodes, deployment artifacts, trust/network boundaries |
| Which domain concepts, attributes and relationships matter? | UML class/domain model diagram | Classes/concepts, associations, inheritance and multiplicities |
| How are persisted entities related? | ER diagram | Entities, keys, cardinality and optionality |
| What goals do different actors pursue with the system? | UML use-case diagram | Actor-to-goal relationships and system scope, not a step sequence |
| Where does data originate, change, and end up? | Data-flow, pipeline or data-lineage diagram | Data objects, stores, transformations and provenance |
| How does a system protect or isolate information? | Trust-boundary/data-flow or security architecture diagram | Flows crossing explicit boundaries and their controls |
| How are topics, categories, causes or responsibilities organized? | Tree, mind map, dependency graph or cause-and-effect diagram | Hierarchy or causal/relational structure without fabricated chronology |
| What occurs over time or overlaps in a plan? | Timeline; Gantt chart | Intervals, milestones, dependencies and concurrent work |
| Which alternatives differ on several dimensions? | Matrix, table or comparison diagram | Comparable criteria; often clearer than a process graph |

A user may need another form or a deliberate combination. Choose the representation because it explains the content, not because it appears in this table.

## Resolve competing choices

Find the main question and choose the form that makes its important relationships easiest to trace:

- A request lifecycle with retries may be a **sequence diagram** when callback timing is central, or a **swimlane** when ownership and operational handoffs are central.
- A processing pipeline may be a **data-flow diagram** when the changing payload matters, or an **activity diagram** when decisions and concurrency dominate.
- “Architecture” may mean logical services, physical deployment, domain relationships, or one request's execution. Use the supplied content to resolve the meaning; ask only when the unresolved interpretation would materially change the authorized deliverable.
- An entity that is pending, running, cancelled, or completed usually needs a **state machine**, not a chain of boxes that confuses states with actions.
- A structure-only system map should not acquire a left-to-right runtime sequence without supporting evidence.

Use a primary diagram plus a focused secondary view only when one view cannot answer a material part of the requested scope legibly. Honor single-page and other output constraints; do not automatically create an architecture/sequence/state bundle or silently replace the requested artifact. Reuse terminology across views and label each view's purpose.

## Keep notation and visual storytelling compatible

Use [visual-storytelling.md](visual-storytelling.md) for the default object/state treatment of new explanatory flows. Choosing flowcharts, swimlanes, lifecycle or architecture flows does not opt out of this default, even without an explicit pictorial request. Preserve formal semantics and the main skill's task-grounded exceptions; apply meaningful contents or payload illustrations wherever compatible. This does not require icons everywhere:

- A UML class box's name, attributes and operations carry structural information; a server icon does not replace its associations or multiplicities.
- A sequence message's sender/receiver and order matter more than an envelope illustration. Optional payload graphics should not hide lifelines, guards, replies or time ordering.
- A state is a condition of an entity, not an executable worker; transition labels should preserve event/guard/action meaning where used.
- An activity fork/join expresses concurrency; several adjacent workers alone do not.
- ER keys and cardinalities, deployment nodes, ports/interfaces, and trust boundaries remain explicit when relevant.

Use a clear legend for nonstandard symbols and label illustrative quantities. Preserve the user's chosen formal notation even when a more pictorial presentation would be attractive.

## Check the choice during normal QA

Can the intended reader answer the main question by following the form's visual organization? Check the appropriate semantics: ownership in swimlanes, ordered interactions in sequence diagrams, valid transitions in state machines, relationships/cardinality in class or ER diagrams, and nodes/boundaries in deployment views. Geometric cleanliness alone does not establish a suitable presentation.

Do not apply runtime reachability rules to a structural model indiscriminately. Use the main skill's topology checks for directed process paths and explicitly required relationships; isolated classes, lifelines, lane labels, or independent structures are not automatically errors.
