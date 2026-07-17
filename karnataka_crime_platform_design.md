# Intelligent Conversational AI & Crime Analytics Platform
## Design Documentation — Karnataka Police Datathon

**Document type:** Working architecture & design record
**Scope:** Challenge framing through data layer, every analytical feature, the conversational/rendering layer, and the cross-cutting governance model.
**Note on data:** Wherever synthetic data is discussed below, the principle applied throughout is: *fill structural gaps freely (thin narrative text, missing volume), never fabricate a distribution that contradicts known reality (e.g. outcome rates).* This is called out explicitly wherever it matters.

---

## 1. Challenge Overview

### 1.1 Problem statement

The challenge — "Intelligent Conversational AI and Crime Analytics Platform" — asks for a system that goes beyond simple data retrieval over a state crime database, enabling:

- Crime pattern discovery
- Criminal network analysis
- Socio-demographic crime insights
- Behavioral and criminological profiling
- Proactive crime prevention intelligence

Ten required capability areas:

1. Conversational Crime Intelligence Interface
2. Criminal Network & Relationship Analysis
3. Crime Pattern & Trend Analytics
4. Sociological Crime Insights
5. Criminology-Based Offender Profiling
6. Investigator Decision Support
7. Financial Crime & Transaction Link Analysis
8. Crime Forecasting & Early Warning
9. Explainable AI & Transparent Analytics
10. Secure Role-Based Access & Governance

### 1.2 Scope constraints

- **Format:** hackathon/datathon — the build must be based on publicly available data, not on KSP's internal systems.
- **Geographic scope:** Karnataka (challenge run by Karnataka State Police).
- **Hard requirements from the PS:** English + Kannada language support, voice Q&A, context-aware follow-up conversations (no need to repeat context), and export of conversation history to a local PDF.

### 1.3 Core architectural commitment: deterministic-agentic design

Established early and held throughout every feature in this document:

> **The LLM plans and narrates. Deterministic tools compute.**

Every analytical capability below (graph algorithms, forecasting models, risk scoring, regression, financial-pattern detection) is a fixed, versioned, deterministic tool — never an LLM improvising a number or a claim from free recall. The LLM's job is to decide *which* tool(s) a query needs, call them, and narrate the result in plain language.

This is paired with a **header/footer guardrail architecture**: every claim the LLM makes in its narration is checked against the actual tool outputs before being surfaced, giving claim-level reproducibility without requiring full token-level determinism. This is the mechanism that makes capability #9 (Explainable AI) real rather than a disclaimer — see Section 11.

---

## 2. Data Ingestion & Processing Layer

### 2.1 Two axes of data

**Static ↔ live (refresh-frequency spectrum):**

| Tier | Examples | Refresh |
|---|---|---|
| Static/reference | Census demographics, NCRB annual reports, district boundaries, socio-economic indices | Yearly or less |
| Slow-moving operational | FIRs, chargesheets, history-sheets, court dispositions | Per-case, effectively immutable once written |
| Live/streaming | New FIR registrations, scraped news, GD entries, financial alerts | Continuous |

**Personal ↔ generalized (granularity spectrum):**

| Level | Examples |
|---|---|
| Individual/case | FIR narrative, accused biodata/history-sheet, statements, MO description, chargesheet, financial transaction trail |
| Location | Crime-scene geocoordinates, PS jurisdiction, hotspot history |
| Aggregate/generalized | District-wise IPC crime counts, NCRB reports, census/NFHS indicators |

### 2.2 File-type taxonomy

| Upload type | Format | Contains | Extraction route | Destination |
|---|---|---|---|---|
| Generalized stats | CSV/XLSX | District-year-crimehead counts, socio-economic indicators | Schema-validated direct load, no LLM needed | `CrimeStatAggregate`, `SocioEconomicIndicator` |
| FIR / e-FIR | PDF (scanned/template) or structured export | IIF-1 shaped fields — FIR no., acts/sections, accused alias/address, MO gist | Layout-aware template extraction, then field mapping; gist chunked + embedded | `Incident`, `Person`, `Location`, `Offense` + vector chunk |
| Chargesheet / judgment | PDF/DOCX free text | Verdict, sections framed, narrative | Targeted extraction for verdict/sections + full-text embed | `Incident` status update + vector |
| History-sheet / biodata | Semi-structured text | Aliases, associates, prior incidents, MO pattern | NER + relation extraction, held for human verification before touching a risk score | `Person`, `CriminalHistory` + graph edges |
| Witness/victim statement | Text or audio | Narrative account | Transcribe if audio, then NER + embed | Vector, linked to incident |
| News article | Scraped HTML | Incident-like info, unverified | NER, held in a staging table — never auto-merged into `Incident` | Staging table pending analyst match |
| Financial transaction | CSV/PDF | Account, amount, date, parties | Structured parse + entity resolution to existing persons | `FinancialTransaction` + graph edges |
| Images | JPG/PNG | Mugshots, scene photos | Object storage + optional captioning/face embedding | `Document` reference, linked to person/incident |
| Audio | WAV/MP3 | Calls, recorded statements | Transcription (Kannada included) → treated as text | Same as statements |
| Geospatial | Shapefile/GeoJSON | Jurisdiction boundaries | GIS load | Referenced by `Location` |

News is the one category kept structurally separate from verified records — it never lands in `Incident` directly, precisely because an unverified media report must not masquerade as a police record.

### 2.3 Real vs. synthetic data sourcing

- A real, publicly downloadable dataset exists: **"FIR DETAILS (KARNATAKA POLICE)" on Kaggle, ~1.6 million real-life records** — this materially reduces how much needs to be synthesized for volume.
- Open aggregate sources: NCRB's "Crime in India" reports and district-wise IPC/SLL datasets on data.gov.in (also mirrored on Kaggle); Census and NFHS-derived socio-economic indicators for district-level correlation work.
- What's realistically only available as synthetic: rich FIR narrative text (if the real dataset's text fields are thin), accused biodata/history-sheets, and financial transaction data (banking data is PMLA-restricted and was never going to be public).
- **Governing principle (established during the investigator-support discussion and re-affirmed for financial crime):** synthesize to fill *structural* gaps (thin narrative text, low volume) freely. Never synthesize a *distribution* that contradicts known reality — e.g., real Karnataka court data shows ~72,000 cases pending trial statewide and roughly 92% of 2023 disposed cases ending in acquittal. A demo that shows a flattering, invented conviction rate is actively misleading for a platform whose own PS scores it on explainability and accountability.
- For financial transaction synthesis specifically, generation should follow real typologies (placement → layering → integration), the same way the published **AMLNet** framework generates realistic laundering transaction flows — not random noise.

### 2.4 Processing pipeline

1. **Type/format classifier** — determines what kind of document this is (generalized stats CSV vs. FIR-shaped PDF vs. free-text history-sheet vs. news article) before choosing an extraction strategy.
2. **Format-specific extraction** — direct load for tabular; layout-aware template extraction for IIF-style forms (tools like Docling/Unstructured); NER/relation extraction for narrative text.
3. **Entity resolution** — the single hardest and most valuable step: the same accused person appearing across multiple FIRs under different aliases/addresses must resolve to one node. This is what makes network analysis and repeat-offender detection possible at all, rather than per-record lookups. (Confirmed as non-optional once the real KSP schema was reviewed — see Section 3.)
4. **Load into the poly-store** — relational for metadata/provenance, vector for semantic search over narrative text, graph for entity relationships.
5. **Audit log** — branches off the extraction stage, recording source, extraction method, and confidence for every derived fact.

### 2.5 Poly-store architecture rationale

The pattern of a relational + vector + graph poly-store (as used by projects like Cognee, which defaults to SQLite + LanceDB + Kuzu) is a strong conceptual fit — crime data is simultaneously graph-shaped (accused↔victim↔location↔financial account), narrative-text-shaped (needs semantic search over MO/gist), and tabular (aggregate stats).

**Recommendation: borrow the pattern, don't depend on the library itself.** Running three embedded stores simultaneously is resource-heavy, coordination across them is fragile, and a small-org-maintained graph backend fork is a bus-factor risk for a deadline-bound build. More importantly, a platform that has to satisfy law-enforcement accountability requirements needs the extraction → entity-resolution → provenance-tagging logic to be fully inspectable — not living inside a third-party memory framework's internals. Build the same three-store split directly (e.g. Postgres/pgvector or SQLite/LanceDB for vectors, Neo4j/Kuzu for the graph).

---

## 3. Schema Architecture

### 3.1 Original target schema (as designed before real data was available)

**Relational core** (adapted from the NIBRS incident-segmentation model — one incident, several linked segments, rather than one flat crime-record row):

| Table | Key fields |
|---|---|
| `Incident` | incident_id, fir_number, ps_id, district_id, date_reported, date_occurred, gd_number, source_type, status, acts_sections[] |
| `Offense` | offense_id, incident_id, crime_head, attempted_or_completed, weapon_used, mo_text |
| `Location` | location_id, incident_id, lat/long, address_text, place_type, jurisdiction |
| `Person` | person_id, name, aliases[], age, sex, nationality, permanent/present address |
| `Case_Person_Role` | incident_id, person_id, role (accused/victim/witness/complainant), arrest_details |
| `Property` | property_id, incident_id, type, value, description |
| `FinancialTransaction` | txn_id, from_account, to_account, amount, date, linked_person_id, linked_incident_id |
| `CriminalHistory` | person_id, prior_incident_ids[], mo_pattern_summary, risk_score (always paired with the evidence that produced it) |
| `SocioEconomicIndicator` | district_id, year, literacy_rate, unemployment_rate, urbanization_pct, population_density |
| `CrimeStatAggregate` | district_id, year, crime_head, count |
| `Document` | document_id, source_type, file_format, ingestion_ts, extraction_method, confidence_score, linked_incident_id, raw_file_ref, human_verified — the provenance backbone |

**Graph layer:** nodes — Person, Incident, Location, FinancialAccount, Organization. Edges — ACCUSED_IN, VICTIM_IN, WITNESSED, OCCURRED_AT, ASSOCIATED_WITH (weighted by co-occurrence), TRANSACTED_WITH, ALIAS_OF (pending-merge candidate), MEMBER_OF.

**Vector layer:** one record per narrative chunk — embedding, source document_id, incident_id, chunk_type (MO/gist/statement/chargesheet/news).

### 3.2 Real KSP schema (ground truth, from the uploaded ER documentation)

A real Karnataka Police FIR system ER document was reviewed. Key tables: `CaseMaster`, `ComplainantDetails`, `ActSectionAssociation`, `Victim`, `Accused`, `ArrestSurrender`, `Act`, `Section`, `CrimeHeadActSection`, `CrimeHead`, `CrimeSubHead`, `CasteMaster`, `ReligionMaster`, `OccupationMaster`, `CaseStatusMaster`, `Court`, `District`, `State`, `Unit`, `UnitType`, `Rank`, `Designation`, `Employee`, `CaseCategory`, `GravityOffence`, `ChargesheetDetails`.

The document was confirmed to be a 9-page, text-only Word-authored specification (no embedded diagram image, despite the filename) — table definitions plus a full foreign-key relationship matrix.

### 3.3 Reconciliation

| Our design | Real KSP equivalent | Verdict |
|---|---|---|
| `Incident` | `CaseMaster` | Matches closely — `CrimeNo` even encodes category+district+station+year in one string |
| `Person` + `Case_Person_Role` | `Accused`, `Victim`, `ComplainantDetails` (three separate, unconnected tables) | **Our entity-resolution layer is required, not optional** — the real schema has no unified person identity across cases at all |
| `Offense` | `CaseMaster.CrimeMajorHeadID`/`CrimeMinorHeadID` + `ActSectionAssociation` | Real version is *more* normalized than ours — adopt their `Act`/`Section`/`ActSectionAssociation` instead of a flat `acts_sections[]` array |
| MO/gist text for embedding | `CaseMaster.BriefFacts` | Confirmed present — this is the field the vector store embeds |
| `Location` | `CaseMaster.latitude/longitude` + date range | Present, though distributed slightly differently than assumed |
| `CaseStageEvent` (our addition, see Section 8) | `CaseMaster.CaseStatusID` (current value only) | Still needed — the real schema has no status *history*, only current state |
| Case outcome | `ChargesheetDetails.cstype` (Chargesheet / False Case / Undetected) + `csdate` | **Better than assumed** — a genuine three-way disposition signal was already planned around a weaker proxy; use this field directly |
| `FinancialTransaction` | *(absent)* | Confirmed pure addition — banking data was never going to live in a police FIR schema |
| Graph/vector store | *(absent, as expected)* | This is an OLTP schema, not built for network analysis — the poly-store layered on top is still required |

**Sensitive-field flag, now precise:** `ComplainantDetails.ReligionID` and `ComplainantDetails.CasteID` are real, normalized, directly-joinable columns — specifically on the *complainant*. Any access-control layer must name these two columns explicitly, not just gesture at "sensitive fields somewhere in the form."

**New capability unlocked by the real schema:** `Unit.ParentUnit` (self-reference) plus `UnitType.Hierarchy` model a genuine police-station → circle → district jurisdictional hierarchy, richer than the flat `ps_id`/`district_id` originally assumed. This lets network analysis check whether a repeat offender's cases span multiple jurisdictions — itself a signal of organized/mobile criminal activity.

**Open item to confirm with KSP:** `Inv_OccuranceTime` appears in the relationship matrix as a one-to-one child of `CaseMaster` but has no table definition of its own, while `CaseMaster` already carries `IncidentFromDate`/`IncidentToDate`/lat/long directly. Unclear whether one is a denormalized copy of the other, or whether this is a documentation gap — worth asking directly rather than guessing.

### 3.4 Net effect of the reconciliation

The real schema is the better **system-of-record** — defer to it wherever it overlaps with our design (normalized Act/Section, `cstype`, `GravityOffenceID` as a real severity anchor, the Unit hierarchy). It was never going to cover network analysis, vector search, cross-case identity, or history of any field — that's not a gap in their design, it's simply outside an OLTP FIR system's job. Our poly-store (`Person` + graph + vector + versioned derived-data tables) remains the necessary layer on top, now with an exact mapping from their three separate person-tables into it instead of an assumed IIF-form structure.

---

## 4. Criminal Network & Relationship Analysis

**Construction:** project the bipartite accused↔incident relation (`Case_Person_Role`) into a person-person **co-offending network** — an edge exists whenever two people appear as accused in the same incident. This bipartite-to-co-offending projection is the standard approach for applying social-network-analysis machinery to police data.

**Techniques:**
- **Community detection** (Louvain or Girvan-Newman) — surfaces cells/sub-groups rather than treating every accused person as an isolated dot.
- **Centrality measures**, used for different jobs — PageRank/eigenvector centrality tends to surface the operational leader; betweenness centrality surfaces the broker (someone bridging two otherwise-disconnected cells — messengers, money-movers).
- **Link prediction** (GCN-based approaches, e.g. CrimeGraphNet) — surfaces a *plausible but unconfirmed* connection between two people who've never shared an FIR, flagged as a lead with a confidence score, never rendered identically to a confirmed edge.

**Multiplex network:** don't build one generic-edge graph — build one graph with multiple edge types (co-offending, shared financial account, shared address, shared alias-cluster), each contributing differently to an overall relationship-strength score. A financial link and a co-arrest are different strengths of evidence and should stay distinguishable.

**Visualization:** force-directed graph, node size by centrality, plus a **time slider** — criminal networks aren't static, and showing how density or a person's centrality changed over months is a stronger "detection of organized crime" story than one frozen snapshot.

**Data handling:** community IDs, centrality scores, and predicted links are model outputs, not source facts — they get their own edge/attribute type (`predicted_link`, with confidence + source tool run), never blurred with a confirmed `ACCUSED_IN`-grade edge.

---

## 5. Crime Pattern & Trend Analytics

**Core technique — self-exciting spatio-temporal point processes (Hawkes/ETAS):** the criminology-grounded standard for hotspot forecasting, built on **near-repeat victimization theory** — a crime temporarily elevates risk nearby, decaying over time, layered on a slower chronic background rate. Field trials found ETAS-based forecasts predicted 1.4–2.2× as much crime as an experienced analyst using conventional hotspot maps, and dynamic patrols built on those forecasts produced a measured crime reduction, while analyst-intuition patrols showed no significant effect.

**Seasonal/event-based analysis** folds directly into this model rather than needing a separate pipeline — the background-rate term can be conditioned on calendar features (festival dates, weekday/weekend, school terms).

**MO-based crime linkage:** grounded in the two-part criminological assumption that offenders are behaviorally consistent with themselves and distinctive from others. Similarity coefficients (Jaccard, or Bayes-factor-weighted comparison) over structured MO features, then hierarchical clustering to group a whole probable series — this can suggest "these five burglaries are likely one person" *before* anyone's arrested, complementing the network layer's confirmed-record approach.

**Data requirement — new, lightweight:** a features table of rolling incident counts per grid-cell per time-bucket, plus calendar flags (festival, weekday, school-term). Cheap to derive from `Incident` + `Location` + `CrimeStatAggregate`; not a new ingestion source.

---

## 6. Sociological Crime Insights

### 6.1 The design principle that governs everything else in this section

This must be built as a **place-level layer, not a people-level layer.** Two groundings for this:

- **Social disorganization theory** (Shaw & McKay): crime rates track neighborhood conditions, not the personal traits of the people living there — residential location predicts involvement in crime more strongly than an individual's own age, gender, or other personal characteristics.
- **The ecological fallacy** (Robinson, 1950): a correlation computed at the aggregate/district level can have the *opposite sign* from the true relationship at the individual level. Folding demographic correlation into individual profiling would also reproduce the same fairness failure mode described in Section 7 (COMPAS), except worse — group-level correlation used to score an individual by group membership.

**Hard architectural rule:** this feature reads only `SocioEconomicIndicator` and `CrimeStatAggregate` at district-year grain, and **never** joins to `Person` or `Case_Person_Role`.

**Where individual-level demographics legitimately belong:** victim-side, in aggregate — age/gender cohort breakdowns of who gets victimized by which crime type, used for resource allocation (patrols, helplines, lighting) — a genuinely useful, low-risk pattern, and an actual track in KSP's own prior datathon. Using the same demographic logic to score an *accused* person's likelihood of offending is not acceptable.

### 6.2 Techniques

- **Composite district stress/vulnerability index** — combine multiple socio-economic indicators (literacy, unemployment, urbanization %, sex ratio) via PCA or percentile-ranking into one or a few composite axes per district, rather than showing ten separate noisy charts.
- **Correlate against CHI-weighted crime harm**, not raw counts (reusing the Crime Harm Index concept from Section 7).
- **Geographically Weighted Regression (GWR)** instead of one global regression coefficient — the relationship between (e.g.) unemployment and crime isn't constant across a state; GWR fits a locally-varying coefficient, producing a map of where a factor predicts crime strongly vs. weakly. A directly relevant Indian precedent exists: a factor-analysis + GWR study on crimes against women in West Bengal did exactly this kind of spatially-varying risk-factor mapping.
- **Feed-forward integration (the genuinely novel part):** rather than a separate isolated dashboard, the district stress index becomes a covariate in the *same* Hawkes/ETAS background-rate term from Section 5 — self-exciting point processes are explicitly designed to accept spatial covariates. "This area's elevated risk is partly chronic (socio-economic) and partly acute (near-repeat)" becomes one decomposed answer.
- **Urbanization/migration as a before/after story**, not a static correlation — tracking crime trend shifts around known rapid-urbanization events (a new industrial corridor, an IT-hub expansion), which is what social disorganization theory actually predicts (population turnover weakening informal social control).

### 6.3 Data & frontend

- New versioned **district composite index** reference table, computed periodically (like a reference artifact, not a live query).
- GWR/regression outputs stored as versioned insight artifacts (coefficient-by-district, run timestamp, data version).
- Frontend: a distinct **policy/prevention dashboard** (choropleths, GWR coefficient maps, toggleable overlays), structurally separate from the case-investigation dashboard — reinforcing the individual/aggregate firewall at the product level, not just the data level.

---

## 7. Criminology-Based Offender Profiling (Risk Scoring)

### 7.1 What goes into the score

**Central Eight risk factors** (Andrews & Bonta) — Big Four: criminal history (the *only static* factor), antisocial personality pattern, antisocial cognition, antisocial associates. Moderate Four: family/marital circumstances, education/employment, leisure/recreation, substance abuse. Only 2–3 of these are reliably observable from police records — criminal history and criminal associates (via the network graph) — and the design is honest about that rather than fabricating placeholder values for the rest.

### 7.2 Severity weighting

**Crime Harm Index (CHI):** weight each offense by sentencing-days-equivalent harm rather than raw counts, so five thefts don't score the same as one attempted murder just because "five > one." A provisional **Indian transposition already exists** — Cambridge's Institute of Criminology mapped NCRB's IPC crime-head statistics onto comparable sentencing-guideline categories, at the direct request of India's National Police Academy. The real schema's `GravityOffenceID` (Heinous/Non-Heinous) gives a real starting anchor for this weighting, keyed to `CrimeSubHeadID`.

### 7.3 Fairness — non-negotiable design constraints

The COMPAS/ProPublica finding: Black defendants were nearly twice as likely to be wrongly flagged high-risk among people never re-arrested, while the vendor's own accuracy-per-score-band metric held up. **Both were right** — equal error rates ("separation") and equal predictive accuracy given a score ("calibration") are two different fairness definitions that, when base rates differ across groups, mathematically cannot both be satisfied at once. This is a property to make a deliberate, disclosed choice about, not a bug to engineer away.

Concrete constraints this produces:
- Protected attributes (the real schema's `ComplainantDetails.ReligionID`/`CasteID`, and any Accused-side equivalents) never go in as model features.
- Whatever subgroup breakdown is ethically relevant (e.g. district) gets an error-rate audit before being called "validated."
- The score prioritizes investigative *attention*, never a standalone decision — always paired with human sign-off, the same checkpoint the ingestion layer already requires for anything derived rather than directly recorded.

### 7.4 Concrete feature construction (all reused from earlier layers, no new ingestion)

- **Severity-weighted history** — CHI-weighted harm across a person's incidents, with a recency decay (reusing the same exponential-decay logic as the Hawkes forecasting tool).
- **Network position** — centrality score from Section 4.
- **MO consistency/escalation** — from the MO-linkage tool in Section 5.
- **Associate risk** — average risk score of a person's direct graph neighbors, the closest observable proxy for the "antisocial associates" factor.

**Output:** never a bare number — a SHAP-style decomposition showing exactly how much each input contributed. Stored versioned (model version, feature values, contribution breakdown, `human_reviewed` flag), never overwriting the previous score, so an investigator can see a risk trend and *why* it moved.

---

## 8. Investigator Decision Support

### 8.1 Subagent architecture

Consistent with a four-agent (Query/Analysis/Synthesis/Alert) pattern established in earlier design sessions for this project, specialized here as:

- **Timeline/brief subagent** — pulls every `Document` linked to an `incident_id`, orders chronologically, compresses each into a summary line. This is *grounded compression* of already-extracted text, not free generation — keeping hallucination risk low.
- **Similar-case subagent** — RAG over the vector store: embed FIR/case narratives, retrieve top-k similar, generate a grounded summary from the retrieved set only. Directly relevant precedent: a 2025 paper applying exactly this retrieve-then-summarize pattern to Calcutta High Court judgment retrieval. Also reuses the MO-linkage clustering tool for behavioral (not just textual) similarity.
- **Lead-recommendation subagent** — every surfaced lead must be the output of an already-built deterministic tool (a predicted network link, a shared financial account, an MO-cluster match) — never an LLM guessing from vibes. Each lead carries its source tool and confidence score.
- **Synthesis** — merges the three subagent outputs into one case brief, run through the same footer claim-validator as everything else.

"One-click" means a **fixed** fan-out to these fixed subagents every time — not an open-ended agent improvising a different research plan per query, which would break the reliability story built everywhere else in this system.

### 8.2 Data reality check (governs this feature's outcome framing)

The real ~1.6M-record Karnataka FIR dataset (Section 2.3) reduces how much needs synthesizing here. But real Karnataka court data shows most cases still pending trial and ~92% of disposed 2023 cases ending in acquittal. **Decision: do not model conviction/acquittal at all for now** — the FIR-level data can honestly support registered → investigation → chargesheet filed → closed, but conviction data lives in a genuinely separate system (e-Courts/NJDG), not a missing column. "Similar past cases" should honestly show procedural status (chargesheet rate, still-under-investigation) rather than implying a conviction likelihood the data can't support.

**Update following the real KSP schema review:** `ChargesheetDetails.cstype` (Chargesheet / False Case / Undetected) with `csdate` is a real, already-available field — better than the proxy originally planned. Use it directly as the case-disposition signal rather than inferring disposition from a status-history proxy.

### 8.3 Schema additions (agreed: no separate database — everything below sits on the existing schema)

- **`CaseStageEvent`** — event_id, incident_id (FK), stage (registered/investigation/chargesheet_filed/disposed), event_date, source_document_id (FK, nullable), confidence. Populates itself from ingestion extraction steps already built (e.g. a chargesheet PDF being ingested writes a `chargesheet_filed` event). `Incident.status` becomes a convenience view of the latest event, not the source of truth — needed because the real schema's `CaseStatusID` only stores current state, no history.
- **`MOLinkageCluster`** — offense_id, cluster_id, similarity_score, model_version, computed_at — versioned the same way as risk scores and predicted links, never a static field bolted onto `Offense`.

---

## 9. Financial Crime & Transaction Link Analysis

### 9.1 Data sourcing

Real transaction data isn't obtainable for a hackathon (PMLA-restricted) — this is the one category where synthetic generation is the only option, done via **typology-driven generation** (as in the published AMLNet framework) rather than random noise, following the three real phases of money laundering: placement, layering, integration.

### 9.2 Real typologies (India-grounded)

- **Structuring/smurfing** — splitting a large sum across deposits just under India's real ₹10 lakh cash-transaction reporting threshold (which triggers a mandatory Cash Transaction Report to FIU-IND).
- **Funnel/mule accounts** — a dormant account suddenly receiving money from many sources, then emptying out immediately — a documented real-world Suspicious Transaction Report trigger.
- **Layering** — money moving through a chain of intermediary accounts, often looping back toward its source.

### 9.3 Detection — reuses the network-analysis toolkit, doesn't duplicate it

Every one of these typologies is fundamentally a **shape** in a transaction graph, not a property of any single transaction: structuring is a fan-out, a funnel account is fan-in-then-fan-out, layering is a cycle or long chain. Detection is mostly the same graph-algorithm toolkit from Section 4 (cycle detection, in/out-degree ratio, community detection) applied to the `TRANSACTED_WITH` edge type, plus cheap deterministic threshold rules mirroring real STR triggers (the ₹10 lakh structuring check, rolling 7-/30-day aggregates).

### 9.4 Integration points (no new architecture required)

- `TRANSACTED_WITH` edges are already one of the multiplex-graph edge types from Section 4.
- Feeds the lead-recommendation subagent (Section 8) directly.
- Feeds the risk-profiling "associate risk" feature (Section 7) — this is *direct case evidence* (a confirmed `FinancialTransaction.linked_person_id`), distinct from the socio-economic aggregate data, which stays walled off per Section 6.

### 9.5 "Integrate with financial crime investigation workflows"

Don't overclaim actual FIU-IND filing integration — that's a regulated system outside this project's authority. Instead, shape the output object the way a real STR is shaped: typology detected, accounts/persons involved, evidence trail, confidence — recognizable to how investigators already work, rather than an invented alert format.

---

## 10. Dynamic Conversational Layer (Generative UI)

### 10.1 The design fork, and which side of it to take

Industry term: **Generative UI** (or Agent-Driven UI). One approach lets the model generate raw rendering code on the fly; the other has the model pick from a **fixed, pre-built catalog of components** and only supply data. Current production systems (Vercel AI SDK, Google's A2UI, LangGraph) have converged on the constrained approach for safety and consistency.

**For this project, this isn't a style choice — it's the same deterministic-agentic principle from Section 1, moved one layer forward.** A law-enforcement tool that regenerates its own rendering code fresh every response is unauditable — you can't certify a chart's correctness if its code didn't exist five seconds ago. Fixed tools compute, fixed widgets render, the LLM only chooses and narrates.

### 10.2 Widget catalog (mapping existing tool outputs to fixed components)

| Tool output | Widget |
|---|---|
| Network analysis (community, centrality, link prediction) | Interactive force-directed graph, node size by centrality, time slider |
| Hotspot forecast (Hawkes/ETAS) | Map with heatmap layer + time-scrubber, background vs. near-repeat decomposition on hover |
| Case timeline subagent | Chronological timeline, each entry linked to its source document |
| Risk profiling | SHAP-style decomposition card |
| Socio-economic/GWR layer | Choropleth with toggleable indicator overlay |
| Financial link analysis | Flow/Sankey-style diagram of the transaction graph |
| Similar-case retrieval | Ranked comparison list with outcome/status per case |

Nothing here is new backend work — every one of these outputs already exists from the features built in Sections 4–9; this layer is a mapping, not a new system.

### 10.3 Making it feel live

- **Stream, don't block** — show a widget's loading/skeleton state the moment a tool call starts (a GWR fit or Hawkes forecast isn't instant), then push real data in when it resolves. This pattern is directly supported by current frameworks (e.g. LangGraph's `push_ui_message`).
- **Two-way, not one-way** — clicking a node in a rendered network graph, or a cell in a hotspot map, fires a new query back into the same conversation ("tell me more about this person," "why is this flagged"), closing the loop rather than leaving the visualization inert.
- **Backend recommendation:** since essentially every tool built across this whole system (graph algorithms, GWR, the point-process model, MO-linkage clustering) is naturally Python tooling, LangGraph's generative-UI support is a more natural fit than the Vercel AI SDK route, which assumes a Next.js/TypeScript tool layer.

### 10.4 Proactive suggestions

Since the planner already knows what it just rendered and what tools exist, it can propose 2–3 concrete next actions as clickable suggestions after each answer ("run MO-linkage on this incident," "show this person's network position") — each mapped directly to a specific tool call, rather than leaving the investigator to guess what's possible.

### 10.5 Explainability tie-in

Every rendered node, edge, or map cell must carry a reference back to its source record — clicking anything should answer "why is this here." This means the conversational layer is doing double duty: it satisfies capability #1 (Conversational Interface) *and* capability #9 (Explainable AI — "visualization of reasoning paths and correlations") simultaneously, rather than being two separate build efforts.

---

## 11. Explainable AI & Governance (cross-cutting, not a separate module)

This was never a single feature to bolt on — it's the architectural commitment running through every section above:

- **Header/footer claim-validation** (Section 1.3) — every LLM claim checked against actual tool outputs before being surfaced.
- **The `Document` provenance table** (Section 3.1) — document_id, source_type, extraction_method, confidence_score, human_verified — backs every fact that entered the system through ingestion.
- **Versioned, never-overwritten derived data** — risk scores (Section 7), predicted network links (Section 4), MO-linkage clusters (Sections 5 & 8), GWR/regression outputs (Section 6) all carry a model version and timestamp rather than replacing history, so any derived claim can be traced to exactly which model run produced it.
- **Named, specific access-control flags** — `ComplainantDetails.ReligionID`/`CasteID` (Section 3.3), never a generic "watch for sensitive fields" gesture.
- **Widget-level traceability** (Section 10.5) — the explainability commitment extends to the rendering layer, not just the text narration.

---

## 12. Cross-Feature Integration Map

| Feeds into → | Network Analysis | Trend/Forecast | Sociological | Risk Profiling | Investigator Support | Financial Crime | Generative UI |
|---|---|---|---|---|---|---|---|
| **Ingestion/poly-store** | Person, graph edges | Incident, Location | SocioEconomicIndicator, CrimeStatAggregate | CriminalHistory | Document, vector store | FinancialTransaction | (all tool outputs) |
| **Network Analysis** | — | — | — | Centrality → associate/network feature | Lead-recommendation subagent | Shares multiplex graph (`TRANSACTED_WITH`) | Force-directed graph widget |
| **Trend/Forecast (Hawkes)** | — | — | Receives district stress index as covariate | — | — | — | Hotspot map widget |
| **Sociological** | *(walled off — never feeds individual scoring)* | Feeds background-rate covariate | — | *(walled off)* | *(walled off)* | *(walled off)* | Choropleth widget |
| **Risk Profiling** | Consumes centrality | — | *(never consumes)* | — | Provides risk context to case brief | Consumes confirmed financial links | Profile card widget |
| **Investigator Support** | Consumes predicted links | Consumes MO-linkage | — | Consumes risk score | — | Consumes financial leads | Timeline + comparison widgets |
| **Financial Crime** | Contributes `TRANSACTED_WITH` edges | — | — | Contributes associate-risk evidence | Contributes leads | — | Flow diagram widget |

The one deliberate non-connection in this table (Sociological → everything individual-level) is the ecological-fallacy/fairness firewall from Section 6 — worth keeping visible precisely because it's the one place features *don't* talk to each other.

---

## 13. Open Items / Not Yet Locked

- Confirm with KSP whether `Inv_OccuranceTime` is a source of truth distinct from `CaseMaster`'s own date/location fields, or a documentation artifact (Section 3.3).
- Verify whether the real Kaggle FIR dataset's narrative fields are rich enough for embedding-based retrieval as-is, or need narrative augmentation for a representative subset.
- Exact risk-scoring model choice (logistic regression vs. gradient-boosted tree) not yet decided — a function of remaining build time.
- Exact widget data-contract schemas (the precise JSON each tool must emit to satisfy its widget) not yet specified in detail.
- Whether/when to add court disposition data (conviction/acquittal) later — deliberately deferred, additive path only, not a redesign.
- Full end-to-end worked example (one analyst question traced through every layer to a rendered answer) not yet written out.
