# Technical Narrative and Future Roadmap

**Companion to `SIH_INTERNAL_PITCH_PLAN.md`.** That file is the timed script. This file is the substance behind it: what each piece actually is, why it exists, what order to explain it in, what to demo, and exactly what we are proposing to build and train next.

Nothing here goes on a slide. This is what you need to hold in your head so that any question lands on solid ground.

---

## Part 1 · How to tell the technical story

### The rule: every component is a forced answer to the previous question

Do not present the architecture as a list of technologies. Present it as a chain where each link is unavoidable given the one before it. Told this way, nothing sounds arbitrary and a judge can follow the reasoning without knowing the stack.

```
Records exist but are disconnected
        ↓  so you need a structure that stores relationships as first-class things
A graph, alongside the relational store
        ↓  but who builds and maintains the graph?
Automatic ingestion: the graph is a byproduct of filing an FIR
        ↓  but nobody in a police station writes graph queries
A conversational interface
        ↓  but can an LLM be trusted to query police data?
NO. So: the model plans, verified code computes
        ↓  then what does the verified code actually compute?
Deterministic analytics engines + three models we trained
        ↓  how do you show the answer to a graph question?
Typed interactive widgets, not text
        ↓  who is allowed to see any of this?
Access enforced inside the database, plus a full audit trail
        ↓  and what happens when nobody thinks to ask?
Scheduled detection that raises alerts on its own
        ↓  and where does all of this go?
The three-rung ladder
```

**Say the chain, not the stack.** If someone wants the stack, it is on an appendix slide.

---

## Part 2 · The chain, link by link

For each link: the question it answers, what it actually is, where the innovation sits, the one sentence you say on stage, and the deeper answer if you are pushed.

---

### Link 1 · Why a graph at all

**Question it answers:** why not just a better search box over the existing database?

**What it is:** a polystore. PostgreSQL holds the records and is the source of truth. Neo4j holds the relationships: `Person`, `Incident` and `Account` nodes joined by `ACCUSED_IN`, `VICTIM_IN`, `WITNESSED`, `ASSOCIATED_WITH`, `TRANSACTED_WITH` and `PREDICTED_LINK` edges. pgvector sits inside the same Postgres instance and holds 384-dimensional embeddings of case narratives.

**Where the innovation sits:** it is not novel to use a graph database. What is worth saying is *why three stores and not one*. The questions are genuinely different shapes:

| Question shape | Store | Why not elsewhere |
|---|---|---|
| "What are the facts of this case?" | Postgres | Needs transactional integrity and row-level access control |
| "Who connects to whom, three hops out?" | Neo4j | Variable-depth traversal and cycle detection; recursive SQL does this badly and slowly |
| "What past cases resemble this one?" | pgvector | Nearest-neighbour over meaning, not keywords |

**On stage, one sentence:** "Three stores, because 'what happened' and 'who connects to whom' and 'what resembles this' are three different questions and one engine does all three badly."

**If pushed:** the vector store lives inside the same Postgres instance rather than as a fourth service, which keeps the operational footprint at two databases while giving three capabilities.

---

### Link 2 · The network builds itself

**Question it answers:** who maintains this graph? This is the objection that kills most graph proposals, because the honest answer is usually "an analyst, forever."

**What it is:** a five-stage async ingestion pipeline. Classify, extract, resolve, load, embed.

1. A document arrives: CSV, XLSX, typed PDF, scanned image, handwritten Kannada FIR, or an audio witness statement.
2. Structured formats are parsed directly against a schema, no model call.
3. Scans go through OCR covering ten Indian languages.
4. Named entities are extracted: persons, locations, dates, accounts, evidence identifiers.
5. Entity resolution matches extracted people against persons already on record, rather than creating duplicates.
6. The result lands in **all three stores in one pass**: rows in Postgres, an embedding in pgvector, nodes and edges in Neo4j.

**Where the innovation sits:** not in any single stage, but in the consequence. Because the graph is written as a side effect of ingestion, **nobody curates it.** The network is a byproduct of filing a case. That single property is what makes the system deployable rather than a pilot that decays.

**On stage, one sentence:** "Nobody maintains this network. It is a byproduct of filing a case."

**If pushed on entity resolution:** this is the genuinely hard part and you should say so. Name matching across transliterations, spelling variants and incomplete records is where a graph either becomes real or fills with duplicates. Currently handled by fuzzy matching against existing person records with the resolver forced to run before any person-scoped operation. Improving it is honest near-term work.

---

### Link 3 · The deterministic tool layer

**This is the core innovation. If you have time for one technical idea, this is it.**

**Question it answers:** an investigator cannot write Cypher, so we need natural language. But can a language model be trusted to query police data?

**The answer we chose: no, and we designed around it.**

**What the obvious build would have been:** natural language in, generated SQL or Cypher out, run it, show the result. This is what most text-to-database products do. We rejected it for three specific reasons, and you should be able to give all three:

1. **It is unverifiable.** Nobody can confirm a generated query expressed the question correctly. A subtly wrong join returns a confident, wrong answer.
2. **It is unsafe.** A generated query is arbitrary code against a police database. Every mitigation is a filter on a string.
3. **It is unbounded.** The model can express any query, including ones that cross access boundaries the system is supposed to enforce.

**What we built instead:** a fixed catalogue of roughly 40 tools. Each has a JSON schema, a Python implementation we wrote and audited, and a defined output shape. The model's only power is **choosing which tool to call and with what arguments.** It cannot compose new queries.

The loop:
1. Question plus tool schemas go to the model.
2. Model emits a function call.
3. We dispatch it, with a permission check, to the deterministic implementation.
4. The result streams to the UI as a widget **immediately**, before any narration exists.
5. The result also goes back to the model as a function response.
6. Repeat, up to six rounds, so the model can chain: resolve a name, then use the returned id in the next tool.
7. When the model stops asking for tools, its text is the final answer.

**Three properties this buys, all worth naming:**

- **Every number is traceable.** Not "the AI said 0.71." The risk service returned 0.71, and the tool that produced it is named.
- **Failure degrades toward the truth, not away from it.** Because widgets render before narration, if the model dies mid-answer the graph and the numbers are already on screen. The analysis never depended on the AI.
- **Authorization lives inside the loop, not around it.** Tools check permissions at dispatch. A constable and an SP asking the same question receive different tool output, before the model ever sees it. There is no privileged back door with a chat box on it.

**On stage, one sentence:** "The model chooses which verified tool to run and writes the sentence around what comes back. It never computes."

**If pushed, the strongest phrasing:** "We permit no generated queries. The model's entire authority is picking from a menu we wrote."

---

### Link 4 · What the tools actually compute

**Question it answers:** fine, but is the analysis any good, or is it just database lookups with a chat wrapper?

Eight deterministic engines. Give the shape, not all eight, unless asked.

| Engine | What it does | Method |
|---|---|---|
| Network analysis | Communities, ringleaders, brokers | Louvain for community detection; PageRank for operational leadership; betweenness for the broker bridging two groups |
| Financial crime | Four money-laundering typologies | Structuring, funnel/mule accounts, layering cycles, organised clusters. Rules and graph algorithms, deliberately not ML, so every flag traces to specific transactions |
| Hotspot forecasting | Where next, at 1 km² | Hawkes/ETAS self-exciting point process |
| Risk profiling | Reoffence risk | Random Survival Forest, trained by us (Part 3) |
| MO linkage | Same-offender crime series | TF-IDF plus contrastive projection, trained by us (Part 3) |
| GWR | Locally varying socio-economic effects per district | Geographically weighted regression |
| Temporal trends | Day, month and hour seasonality | Aggregation with explicit coverage reporting |
| Early warning | Standing alerts without being asked | Reuses the network and financial detectors on a schedule |

**Two of these are worth calling out specifically because they carry real intellectual content:**

**Hawkes/ETAS and the chronic/acute split.** A self-exciting point process models crime as partly background rate and partly contagion: one burglary raises the probability of another nearby soon after, which is the near-repeat victimisation effect criminology has documented for decades. Our forecast returns each cell's predicted rate **decomposed into two components**: a chronic background driven by district socio-economic stress, and an acute near-repeat elevation driven by recent incidents.

Why that matters: **the same number implies two different interventions.** A chronically elevated cell needs socio-economic action. An acutely elevated cell needs a patrol this week. A heatmap cannot tell you which. This is the most criminologically literate thing in the system and it costs one sentence to say.

**The financial detectors are deliberately not ML.** Structuring is defined as repeated sub-threshold transfers between the same pair inside a rolling seven-day window, summing over India's ₹10 lakh Cash Transaction Report threshold with at least three legs. A funnel account requires genuine prior dormancy, then a burst from five or more distinct sources within two days, then eighty percent or more leaving within five days. These are rules because **an accusation of money laundering has to trace to specific transaction identifiers**, not to a score. Say that: it demonstrates you understand when not to use ML.

---

### Link 5 · The answer is an object, not a paragraph

**Question it answers:** you asked a question about a network. What does the answer look like?

**What it is:** each tool maps to a typed React widget. A force-directed network, a hotspot map, a money-flow diagram, a risk card with its feature decomposition, a temporal chart, an alert list. Twenty-seven of them. They stream inline in the chat transcript, interleaved with the text.

**Where the innovation sits, and it is real:**

- **The widget is the safety boundary made visible.** Because the model can only call tools, and each tool has a defined output shape, the UI can render structured output rather than parsing prose. The generative UI and the injection-safety property are the same design decision seen from two sides.
- **Every payload is structurally type-guarded on the client.** The renderer checks for the presence of expected fields rather than trusting the declared widget type, so a malformed result degrades to text instead of crashing the transcript.
- **The answer is actionable, not terminal.** Click a node in the graph and you get an entity action menu: open profile, compute risk, check for structuring. Those deep-link into the relevant workspace with the identity carried through. **The investigator never types an identifier.** This is the difference between a demo and a tool, because re-typing UUIDs is exactly where real investigative software dies.
- **Empty results emit no widget.** An empty frame containing null is not a visualization.

**On stage, one sentence:** "The answer is not a paragraph, it is a graph you can click, and clicking keeps the investigation moving without typing an identifier again."

---

### Link 6 · Who is allowed to see what

**Question it answers:** this system knows a great deal about a great many people. What stops misuse?

Four layers, and the second one is the interesting one:

1. **A capability matrix, not a rank ladder.** Seven roles. Named capabilities per role, because specialist roles cut across the hierarchy rather than sitting inside it. The clearest case: a **Policy Maker** sees statewide aggregates and audit logs but is **structurally blocked from individual case PII and from the network graph entirely.** That is not a lower privilege level, it is an orthogonal one, and it exists to prevent the ecological fallacy: "this district has high unemployment and high crime" must never become "this person is unemployed, therefore."

2. **Enforcement inside the database, not in the application.** Row-level security policies on the case and person-role tables filter by the requesting user's rank and district. The API connects as a restricted database role that **cannot bypass those policies**, which matters because a superuser or table owner bypasses row-level security entirely and would turn every isolation policy into a silent no-op. The policies also fail closed: if the session context is missing, the comparison is null, and null comparisons return zero rows rather than every row.

   **On stage:** "A constable's query returns fewer rows than an SP's because the database itself refuses, not because we hid a button in the UI."

3. **Named per-field masking.** There is deliberately no generic "mask everything" helper. Each masked column has its own function. Inside a case workspace, masking degrades to "Victim A" rather than "Redacted", which preserves who-did-what-to-whom while removing identity.

4. **Append-only audit and immutable change history.** Every login, case view, brief generation, export, download, edit and share, with user, IP and device. Separately, a field-level diff log of every human edit to a record: old value, new value, who, when.

**The theme line:** the audit log is already append-only. Hash-chaining each entry to its predecessor makes it **tamper-evident**, so nobody, including an administrator, can quietly alter an access record. That is the property digital evidence chain-of-custody actually needs, and it is a small change to a table we already write.

---

### Link 7 · The system watches when nobody asks

**Question it answers:** everything so far requires someone to ask a question. What about what nobody thought to look for?

**What it is:** the same deterministic detectors, run on a schedule, raising standing alerts. Currently two graph detectors plus the financial scan: persons accused across more than one police jurisdiction, and newly dense co-offending communities.

**Where the innovation sits, and it is a genuinely non-obvious engineering point worth having ready:**

Louvain assigns community identifiers arbitrarily. They differ between runs on the same data. If you key alerts on the community id, **the same criminal crew re-alerts every hour under a new number**, and the feed becomes noise within a day. So each alert carries a fingerprint derived from the sorted membership of the group rather than from the algorithm's label. The group has a stable identity independent of how the algorithm numbered it, and a rescan inserts only genuinely new findings.

This is a good "what was hardest" answer. It shows the difference between running an algorithm and shipping a product built on one.

---

## Part 3 · The models we trained

**This is your team's own ML work and it deserves explicit billing.** Three models, trained from scratch, each evaluated properly. Use the exact numbers below.

### 3.1 The three models

| | Risk | Leads | MO linkage |
|---|---|---|---|
| **Version** | `risk_survival_rsf_v1` | `node2vec_logreg_v1` | `mo_linkage_tfidf_contrastive_v1` |
| **Family** | Random Survival Forest | node2vec embeddings plus logistic regression | TF-IDF plus contrastive Siamese projection |
| **Task** | Time-to-reoffence risk | Plausible unconfirmed relationships | Same-offender crime series |
| **Headline metric** | Held-out concordance **0.7117** | Temporal-holdout AUC **0.7663** | Recall@3 **0.8966** |
| **Baseline it beats** | Severity-only, **0.4964** | Precision@20 of 0.80 | Baseline recall@3 **0.7931** |
| **Training scale** | 606 persons, 417 events, 189 censored | 673 nodes, 38,170 edges | 1,072 pairs, 130 series |

**Points worth making about the evaluation, because evaluation quality is what separates trained models from fitted ones:**

- **The risk model publishes its own baseline.** Concordance 0.71 against a severity-only baseline of 0.50, which is chance. Reporting the baseline next to the score is the honest form and most teams do not do it.
- **Link prediction was evaluated on a temporal holdout, not a random split.** Trained on the graph as it looked at a cutoff date, then scored on the 26 edges that actually formed afterwards. A random split on graph data leaks future structure into training and inflates the number. Saying this out loud signals you know the trap.
- **Feature importance is permutation-based**, and the dominant feature is network centrality at 0.146, well ahead of severity history at 0.019. That is a substantive finding: **who you offend with predicts more than what you have done.** That is a criminologically interesting result and it justifies the whole graph approach from inside the model.
- **Fairness is designed in, not audited afterwards.** Religion and caste are never features in any of the three. Beyond that, the risk model's audit explicitly checks whether centrality carries geography-based proxy signal, because a model can encode a protected attribute without ever seeing it. That is the COMPAS lesson and naming it demonstrates you know the literature.
- **MO linkage takes no demographic input at all.** It operates on modus operandi free text: weapon, entry method, target, time-of-day pattern.

### 3.2 How the models reach the product

Deliberate architectural decision worth explaining: **models are not served live.**

They train offline. Their outputs are synced into the product's own tables and graph: risk scores into a versioned `risk_score` table, predicted links as a distinct `PREDICTED_LINK` edge type in Neo4j, MO clusters into their own table. The bridge maps the pipeline's text identifiers onto the product's UUIDs deterministically using UUID5 against a fixed namespace, so both sides can reproduce the mapping without ever having to agree on an identifier scheme, and no schema change is needed.

**Why this is right, not lazy:**
- Serving is a single indexed read. No inference at query time, which is why cost and energy per query stay flat as usage grows.
- Every score on screen is a **record of what a named model version produced at a named time**, not an unversioned recomputation that could silently change under an investigator.
- Retraining is a batch job, not a deployment.

### 3.3 Model transparency is a product surface

The model cards are inside the product on a `/models` page: family, task, held-out metrics, baseline, feature importances, training scale, fairness posture. The risk score shown to a user carries its model card with it.

**Say this:** "If an officer sees a risk score, they can see in the same interface how good that model is, what drove it, and what it refuses to do."

### 3.4 The honesty position on data

**Do not fudge this. State it plainly and move on.**

> "The models are trained on a synthetic dataset we generated: 800 persons, 1,500 incidents over 24 months, 130 ground-truth MO series, with persistent co-offending crews so the network has real community structure to learn. The 31 districts are real Karnataka districts and the socio-economic priors are NCRB and NDAP derived. The geographic coordinates are synthetic and deliberately so, because we will not put fabricated crime scene locations on a map. What the numbers prove is that the pipeline is correct and the methods work on data with known ground truth. What they do not prove is generalisation to real records. That needs a district data-sharing agreement, and it is the first thing we would ask for."

That paragraph converts your biggest vulnerability into evidence of judgement. A team that says it first is trusted; a team that gets caught is finished.

---

## Part 4 · The demo

**Twenty-five seconds. Pre-recorded. Silent. Captioned. Embedded in the deck file. Never live.**

### 4.1 What to show, in this exact order

| Beat | Screen | What it silently proves |
|---|---|---|
| 1 | Type or speak the question in **Kannada** in the chat | Multilingual, voice, real interface |
| 2 | Tool chips appear in sequence: `search_persons` then `get_ego_network` then `detect_communities` | The agent is **chaining** tools, not doing one lookup. This is the visible proof of the whole tool-layer story |
| 3 | The force-directed network renders **inline**, with communities coloured | Generative UI. The answer is a graph, not text |
| 4 | Click a node. Quick-action menu appears | Interactive, actionable, and no identifier was typed |
| 5 | Risk card opens with its feature decomposition and model card | The trained model, and transparency, in one shot |
| 6 | Follow through to the money-flow diagram | Second analytics domain, financial trail |

Six beats, twenty-five seconds, and it demonstrates: multilingual input, agentic tool chaining, three analytics engines, generative UI, interactivity, deep-linking, a trained model, and model transparency. **No slide can do that.**

### 4.2 Backup shots if you have another ten seconds

- The **alerts page**, to prove the system acts unasked. High value if the automation story lands well with this panel.
- The **model transparency page**, if the judges skew academic.
- The **global network graph** with filters, if they skew visual.

### 4.3 What NOT to demo

- Document upload and ingestion. It is one of your best stories and one of your worst demos, because it is slow and mostly invisible. **Tell it, do not show it.**
- Admin, audit log and user management screens. Important, unphotogenic.
- Anything requiring a typed identifier. It contradicts the point you just made.
- Login. Start the clip already inside the product.

---

## Part 5 · Future work, precisely specified

For each item: what we build, what we train, what data it needs, and the honest hard part. **Be able to answer "what exactly would you train" for every one of these**, because that is the question that separates a vision from a wish.

---

### 5.1 Rung 1 · Call detail records

**What we build:** a CDR ingestion path and a new edge type, `COMMUNICATED_WITH`, carrying frequency, duration, direction and time window, plus tower-location metadata where present.

**What we train:** nothing new initially, and say so. The value is in the data, not a model. The existing community detection, centrality and link prediction run over a richer graph immediately.

**Then what we train:** the link-prediction model gets retrained on the multiplex graph, where an edge can now be co-offending, financial or communication. Communication edges are a strong predictor of association, so we expect the AUC to move.

**Data needed:** CDR extracts under existing lawful-interception authorisation. No new legal instrument, because police already obtain these.

**Why it opens the ladder:** police already do network analysis on CDR dumps, manually, in Excel. It is the most-used investigative dataset in the country and it is completely disconnected from case records. This rung says "we know what you actually do."

**Honest hard part:** CDR volume dwarfs case data. A single tower dump can exceed the entire case graph. This becomes a scale and retention-policy problem, not a modelling problem, and saying that shows you have thought past the demo.

---

### 5.2 Rung 2 · The network as a live instrument

**The innovation beat. The single most distinctive future claim you have.**

**The gap today:** the early-warning scan is scheduled and recomputes over the whole graph. It detects **states**: this community is dense, this person spans jurisdictions. It cannot detect **events**.

**What we build:** incremental graph analysis. When an FIR is written, recompute only the affected neighbourhood rather than the whole graph, and compare the network's structure before and after.

**The specific signal, and this is the sentence to rehearse:**

> **The moment one new edge merges two clusters that were previously separate.**

Two crews with no known connection now have one. Operationally that is a merger, a subcontract, or a shared fence or receiver. It is among the highest-value intelligence events in organised crime, and **nobody detects it today, because existing tools query a graph rather than watch it change shape.**

**What we train:** nothing. This is an algorithms and systems problem, not a learning problem, and saying so is a strength. The relevant area is incremental and dynamic community detection, which is established work, not speculation.

**What it rests on:** two things already built. Community detection already runs. And alerts are already fingerprinted by group membership rather than by algorithm label, which is precisely the mechanism that makes "these two groups became one group" detectable as an event rather than dismissible as relabelling noise.

**Related, and cheap to add once this exists:** temporal networks. The graph builder in our ML pipeline already supports an `as_of_date` snapshot, so "show me this network as it stood in March" and "show me how it formed" are reachable. Network *formation* is how you distinguish a growing syndicate from a stable one, and it is how you argue in court about when someone joined.

**Honest hard part:** thresholds. Not every new edge between clusters is meaningful. Deciding what counts as a merge rather than a coincidence needs calibration against real confirmed cases, which loops back to needing a data partnership.

---

### 5.3 Rung 3 · Working across states without pooling data

**This rung has two genuinely separate parts. Do not merge them, and do not call the whole thing "federated learning", because a knowledgeable judge will separate them and you should be the one who does it first.**

| | **Federated query** | **Federated learning** |
|---|---|---|
| Problem it solves | *Retrieval.* Does this person appear in another state's records? | *Training.* Can a model learn from all states' data without any state exporting it? |
| What moves between states | A query, and a match or no-match | Model weights or gradients. Never data |
| What never moves | Any record | Any record |
| Technique family | Hashed identifier matching, private set intersection | Local training plus federated averaging |
| Delivers | A cross-state network | A better model everywhere |

---

#### 5.3a Federated query

**What we build:** each state runs its own instance. A query propagates to peer instances. **Only matches return, never raw records.**

**The framing that makes this credible:** the obstacle to a national criminal network system is not technology. States will not surrender raw crime records to a central pool, for legal, political and practical reasons. Any pitch that assumes one national database is naive. So the national version *cannot* be centralised, and the interesting question becomes how to answer cross-border questions anyway.

**What it rests on:** we already enforce isolation by rank and district inside the database. Federation across states is that same principle one level up. That is what makes it credible rather than grandiose.

**What we train:** nothing. This is cryptography and systems.

**The honest hard part, and name it before they ask:** matching an identity across states without exchanging the identity. The relevant directions are deterministic hashing of normalised identifiers such as an Aadhaar-derived token or a normalised name-and-date key, and private set intersection where two parties learn only the overlap between their sets and nothing else. Saying "this is the hard part and here is the family of techniques" is far stronger than implying it is easy.

**Theme fit:** privacy-preserving matching between organisations that do not fully trust one another is exactly the Blockchain and Cybersecurity problem space. This is where the theme placement stops being a stretch and becomes the natural home for the work.

---

#### 5.3b Federated learning: exactly what we would train

**Be precise here. Not all three of our models federate equally well, and knowing which is which is the answer that will impress.**

**Start with MO linkage. It is the best candidate by a clear margin, for four reasons:**

1. **It is gradient-based.** TF-IDF features into a contrastive Siamese projection is a neural model trained by gradient descent, so federated averaging applies directly. Each state trains locally on its own case narratives and only weight updates are aggregated.
2. **The thing being learned is genuinely national.** A burglary signature, a specific entry method, a target-selection pattern, is the same behaviour in Karnataka and in Maharashtra. Every state has a small number of series and would benefit from a model shaped by all of them. This is the textbook condition where federated learning actually helps rather than being an architecture flex.
3. **It touches no identities at all.** MO linkage operates on modus operandi free text: weapon, entry method, target, time of day. **No person, no address, no identifier.** The privacy story is trivially clean, which makes it the easiest thing to get a state to agree to.
4. **It is the model most limited by our data volume.** 130 series and 1,072 pairs is small. Federation is the natural fix.

**Say it like this:**

> "The first thing we would federate is MO linkage. Each state trains on its own case narratives, and only model weights are exchanged, never records. It works because a burglary signature is the same behaviour everywhere, and because that model only ever sees the method, never the person."

**Then be accurate about the other two:**

- **Link prediction is partially federatable, and explain why.** The node2vec embedding is specific to one graph's structure and does not transfer to a disjoint graph, so you cannot federate the embedding itself. But the classifier that sits on top, mapping a pair of embeddings to "is this a real edge", learns a relationship that is not state-specific. So: **embeddings stay local, the downstream classifier federates.** Being able to make that distinction unprompted is a strong signal.

- **The Random Survival Forest is the awkward one, and say so.** Tree ensembles do not average like gradients do. Two options: a federated forest where each state contributes trees to a shared ensemble, or switching to a gradient-based survival model such as a Cox neural network, which federates cleanly at some cost in interpretability. **Naming a genuine limitation in your own work and offering two concrete paths is worth more than claiming everything federates.**

**The honest hard part for federated learning specifically:** TF-IDF requires a shared vocabulary across participants, which itself leaks distributional information. The standard fix is feature hashing, which removes the need for a shared vocabulary at some interpretability cost. Also, federated averaging assumes participants' data is not wildly differently distributed, and crime patterns genuinely do differ between states, so this needs measuring rather than assuming.

---

### 5.4 Tamper-evident evidence chain of custody

**What we build:** each audit entry carries the hash of the previous entry, forming a chain. Any alteration or deletion breaks verification at that point and everything after it.

**What we train:** nothing.

**What it rests on:** the audit log is already append-only and already records every access with user, IP, device and reason. This is a column and a verification routine, not a new system.

**Why it matters and why it is the right answer on the theme:** a distributed ledger solves trust between mutually distrusting parties, which is the wrong shape inside a single police force. The property you actually want is tamper-evidence. Extended to evidence handling, this is the chain of custody a court requires.

---

### 5.5 The system compounds

**What we build:** capture investigator judgement. When a predicted link is confirmed or dismissed, when an alert is acted on or discarded, when a suggested MO series is accepted or rejected, that decision is recorded as a labelled example.

**What we train:** everything, on better data. Today's models are trained offline on synthetic ground truth and frozen. Real confirmations are the highest-quality labels obtainable, because they come from the people best placed to judge. This is active learning: the system asks about the cases it is least certain of, and improves fastest where it is currently weakest.

**Why it is the right closing thought:** it converts the product from a tool into an asset. It gets better because it is used. It also creates the fairness feedback loop, because a confirmation-and-dismissal record per district is exactly the data a real fairness audit needs.

**Honest hard part, and it is a real one:** confirmation bias. If investigators confirm the leads the model suggests and never look at the ones it does not, the model learns to predict its own outputs. Mitigations exist, including holding out a random sample of unsuggested pairs for review, but the risk is genuine and naming it is better than pretending it is not there.

---

## Part 6 · Technical Q&A ammunition

**"Isn't this just RAG over a police database?"**
No. RAG retrieves text and lets the model reason over it, which means the model produces the analysis. Here the model produces no analysis at all. It selects a tool, and fixed code computes. There is a vector store, used for similar-case retrieval, but it is one tool among forty rather than the architecture.

**"What stops prompt injection?"**
The model's entire authority is choosing from a fixed menu of tools we wrote. There is no code path from model output to a query. The worst an injection achieves is calling a legitimate tool with different arguments, and that tool still runs its own permission check against the actual logged-in user.

**"Six tool rounds sounds slow."**
Most questions resolve in one or two. The cap exists so a confused model cannot loop forever. And widgets stream as each tool completes, so the investigator sees the network while the model is still writing, rather than waiting for the whole turn.

**"Why not fine-tune a model on police data?"**
Because it would make the problem worse. A fine-tuned model still generates, so the output is still unverifiable, and now the training data is inside the weights and cannot be access-controlled per district. Our approach keeps data in the database where row-level security applies.

**"How do you know your risk model isn't biased?"**
Protected attributes are never features, but that alone is insufficient, because a model can encode a protected attribute through a proxy. So the audit explicitly checks whether centrality, the dominant feature, carries geography-based proxy signal. Beyond that, the model refuses to score anyone whose criminal history has not been human-verified, and every score requires human sign-off. It prioritises attention. It does not decide anything.

**"What was hardest?"**
Two good answers, both true, both non-obvious:
- Community alerts re-firing every hour, because Louvain renumbers communities on every run. Fixed by fingerprinting the group's membership instead of trusting the algorithm's label.
- District isolation silently switching off inside the streaming chat response, because the database session setting is transaction-scoped and the streaming response returns before the generator body runs, committing and clearing the context. Found because a case workspace returned empty only inside chat and nowhere else.

**"Why three databases? Isn't that over-engineered?"**
Two, in fact, since the vector store lives inside Postgres. And the reason is that recursive SQL is genuinely bad at variable-depth traversal and cycle detection, which is exactly what "find circular money flow through two to six accounts" requires.

**"Could a state deploy this tomorrow?"**
No, and here is what stands between: entity resolution needs hardening against real transliteration variance, real geocoded locations are needed to replace synthetic coordinates, and the models need retraining on real records under a data-sharing agreement. The architecture and the analysis do not change. The data does.
