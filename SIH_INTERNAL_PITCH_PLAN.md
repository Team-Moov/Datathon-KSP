# Internal SIH Round: Pitch Plan

**PS SIH26189 · Ministry of Home Affairs · AI-Powered Criminal Network Analysis System · Team Raspberry3.1415**

Format: 5 minutes presentation plus Q&A.

---

## 0. The one thing to understand before changing anything

The internal round and the national round are scored on different questions.

| | National shortlisting | **Internal round** |
|---|---|---|
| The judge is asking | "Is this real and is it right?" | **"Can these five people think, and would I bet on where they're going?"** |
| Built work functions as | The subject of the pitch | **The credential that buys you the right to talk about the future** |
| Wins on | Evidence, validation numbers, honesty about gaps | **Clarity of reasoning, visible decisions, ambition with a mechanism** |
| Time spent on vision | Almost none | **A quarter of the pitch** |

**So the central change is this: stop selling the inventory, start selling the trajectory.** What you have built appears as proof that you execute, spent in about sixty seconds, so that the remaining four minutes can buy something a feature list cannot.

A judge in this room cannot tell a good decision from a lucky one unless you show them the alternative you rejected. That is the single highest-leverage change in this document.

---

## 1. Time budget: what moves

| Beat | National version | **Internal version** | Change |
|---|---|---|---|
| Title | 10s | 10s | same |
| Problem and why this PS | 45s | 55s | +10s |
| Solution and demo | 60s | 60s | same |
| Technical approach | 75s | 55s | **-20s** |
| **Vision ladder** | 0s | **75s** | **+75s** |
| Impact, feasibility, viability | 100s | 35s | **-65s** |
| Close | 10s | 10s | same |
| **Total** | 300s | **300s** | |

Feasibility collapses from a hundred seconds to thirty-five because "we built it and deployed it" is one sentence when nobody is scoring you against an evidence table. That reclaimed time goes almost entirely into trajectory.

---

## 2. What to ADD (not in any current material)

### 2.1 One decision you rejected, said out loud

The highest-value twenty seconds available to you. Goes at the top of the technical approach slide.

> "The obvious way to build this is to let the model write database queries. We rejected that. A generated query is neither safe nor checkable, and in an investigation an answer you cannot verify is worse than no answer at all. So we inverted it."

Why this works: a rubric measuring thought process has no way to observe thinking except through choices, and a choice is only visible when the road not taken is named. Almost no team does this. It also pre-empts the sharpest technical question a judge could ask, in your own framing, before they get to ask it.

### 2.2 The failure mode that would actually kill it

Goes at the end of the feasibility beat.

> "The risk that would actually kill this is not scale and it is not privacy. It is adoption. A system an officer does not trust or cannot operate never gets opened, and then the quality of the analysis is irrelevant."

Why this works: "scalability" and "data privacy" are the rote answers every team gives, and evaluators have stopped hearing them. Naming a real, non-obvious, product-level risk reads as maturity. Your mitigation is already built, which is voice in Kannada and answers that arrive with the underlying records attached rather than as assertions, so the admission costs you nothing.

### 2.3 The vision ladder

Full content in section 4. The rule: **a ladder, not a list.** Each rung must rest on the rung below or on something already built, otherwise it reads as daydreaming and actively loses points.

### 2.4 A closing reframe on compounding

> "Right now our models are trained offline and frozen. The version where a confirmed or dismissed lead becomes a training signal gets better the more it is used."

Answers "what happens in year two" without being asked, and converts the pitch from a tool into an asset in one sentence.

---

## 3. Slide-by-slide run of show

Seven slides. Word counts given because the constraint is spoken words, not slide count. Total spoken material is roughly 690 words, which is the honest ceiling for five minutes at a pace that does not sound rushed.

---

### Slide 1 · Title · 0:00 to 0:10

**On slide**
Sambandh
AI-Powered Criminal Network Analysis System
SIH26189 · Ministry of Home Affairs · Team Raspberry3.1415

**You say**
> "Problem statement 26189, from the Ministry of Home Affairs. Criminal network analysis. I am [name]."

---

### Slide 2 · The problem and why we chose it · 0:10 to 1:05

**On slide**
Headline: **The link is not missing. It is unreachable.**
Visual: three FIR cards side by side, Belagavi, Hubballi, Bengaluru, with one name highlighted in all three in a different role each time. Nothing else.

**You say** *(118 words)*
> "A chain snatching in Belagavi. A stolen two-wheeler in Hubballi. A man arrested in Bengaluru with forty gold chains.
>
> Three FIRs. Three police stations. Three separate files.
>
> One name appears in all three. Accused in the first, a witness in the second, a phone contact in the third.
>
> That connection is already in the police database. It has been there the whole time. Finding it needs an officer who happened to think of it, and days of cross-referencing across stations that do not share a search box.
>
> We chose this problem statement because the gap is not data. India digitised its police records years ago. The gap is that criminal networks are organised and the records are not."

**Why it is built this way:** the last two sentences are the reason-behind-the-idea the brief asks for, and they do more than explain your choice. They reframe the problem so that a graph is the obvious answer. Without that reframe, a judge's default assumption is that you are proposing better search, and better search is what several other teams will propose.

---

### Slide 3 · The solution · 1:05 to 2:05

**On slide**
The question written across the top in Kannada and English.
Four steps: Resolve · Connect · Analyse · Answer.
The demo clip, twenty to twenty-five seconds, pre-recorded and silent, running under your final two sentences.

**You say** *(136 words)*
> "So we made the records answer questions.
>
> An officer asks, in Kannada or English, by voice or by typing: who is behind the chain snatchings in Belagavi?
>
> The system resolves that name to a real person record. It never guesses an identity. Then it pulls everyone connected to them: shared cases, shared addresses, shared bank transfers.
>
> Then it does the part a human cannot do by eye. Which cluster is a crew. Who the ringleader is. Who the quiet person is bridging two groups that should not know each other.
>
> And the answer is not a paragraph. It is a graph you can click. Click a node and you are in that person's profile, their risk, their money trail, without typing anything again.
>
> And you do not have to ask. The same checks run on a schedule, so when a group starts forming, the alert comes to you."

---

### Slide 4 · Technical approach · 2:05 to 3:00

**On slide**
Headline: **We rejected the obvious build.**
Then two lines only:
1. The AI never computes.
2. The network builds itself.

No stack logos. No architecture diagram. Those go in the appendix.

**You say** *(128 words)*
> "The obvious way to build this is to let the model write database queries. We rejected that. A generated query is neither safe nor checkable, and in an investigation an answer you cannot verify is worse than no answer.
>
> So we inverted it. The model can only call tools we wrote and audited. It chooses which one to run and writes the sentence around what comes back. Every number on screen comes from fixed code. If the AI fails halfway through an answer, the graph and the numbers are already on screen, because the analysis never depended on it.
>
> Second: the network builds itself. An FIR arrives, typed, scanned, or Kannada handwriting. We read it, pull out the people and the accounts, match them against existing records, and write them into the graph. Nobody maintains this network. It is a byproduct of filing a case."

**Optional line if the theme comes up:** our audit log is already append-only, and hash-chaining each entry to the one before it makes it tamper-evident, which is the chain of custody digital evidence actually needs.

---

### Slide 5 · Where this goes · 3:00 to 4:15

**This is the centrepiece of the internal pitch. Design the slide accordingly: three rungs ascending, not three boxes in a row. The visual should say "ladder."**

**On slide**
1. Call detail records
2. The network as a live instrument
3. Federation without centralisation

**You say** *(170 words)*
> "What we have built is one state and one kind of data. Here is where it goes.
>
> **First, call detail records.** Police already do criminal network analysis today. They do it in Excel, on CDR dumps, by hand. It is the most-used investigative data in the country and it is completely disconnected from case records. For us it is one more edge type on a graph that already exists.
>
> **Second, and this is the part we care most about.** Right now our scan runs on a schedule. It should be continuous. When an FIR is filed, recompute only the part of the network it touches, and watch for structural change instead of thresholds. The signal we want is the moment one new edge merges two clusters that were separate. That is a bridge forming between two crews. It is one of the highest-value events in organised crime and nobody detects it today, because nobody is watching the shape of the graph change.
>
> **Third, the national version.** States will not pool raw crime data, and that is law and politics, not a technical gap. So it cannot be one large database. Each state runs its own instance, queries travel between them, and only matches come back, never records. We already isolate by district. This is the same idea one level up."

---

### Slide 6 · Feasibility, viability, usefulness · 4:15 to 4:50

**On slide**
Built and deployed · ₹500 to ₹11,000 per month · No new data collection · Adoption is the real risk

**You say** *(82 words)*
> "It is built and deployed. Live link and demo video are in the deck.
>
> It runs on roughly ₹500 to ₹11,000 a month, and that cost stays flat as usage grows, because nothing expensive runs at query time.
>
> It needs no new data collection. It runs on records the state already holds.
>
> And the risk that would actually kill this is not scale and it is not privacy. It is adoption. A system an officer does not trust or cannot operate never gets opened. That is why it speaks Kannada, and why every answer arrives with the records attached."

---

### Slide 7 · Close · 4:50 to 5:00

**On slide**
**The network is already in the data.**

**You say**
> "Right now our models are trained offline and frozen. The version where a confirmed or dismissed lead becomes a training signal gets better the more it is used.
>
> The network is already in the data. We make it visible, checkable, and watched. Thank you."

---

## 4. The vision ladder in full

This section is for your own preparation. Do not put this level of detail on a slide. It is what you need to hold in your head so the ladder survives questioning.

### Rung 1 · Call detail records
**Near term. Deliberately humble, and that is the point.**

CDR analysis is what Indian police actually do for network analysis right now, and they do it manually in spreadsheets. Tower dumps and call records are the most-used investigative dataset in the country. They are entirely disconnected from case records.

- **What it rests on:** your graph already models people and edges between them. A call is an edge type.
- **Why it convinces:** it proves you understand the real workflow rather than an imagined one. Any judge with police contact recognises it instantly.
- **Why it opens the ladder:** starting with something modest and obviously buildable earns you the credibility to make the third claim.

### Rung 2 · The network as a live instrument
**The innovation beat. This is the sentence a judge repeats afterwards.**

Today the early-warning scan is scheduled and runs across the whole graph. The version worth describing is incremental: an incoming FIR triggers recomputation only of the neighbourhood it touches, and the system watches for **structural events** rather than numeric thresholds.

The specific event to name out loud: **the moment a single new edge merges two previously separate clusters.**

- **What that means operationally:** two crews that had no known connection now have one. In organised crime that is a merger, a subcontract, or a shared fence, and it is among the highest-value intelligence events there is.
- **Why nobody has it:** existing tools query a graph. They do not watch it change shape.
- **What it rests on:** you already run community detection and you already fingerprint groups by membership rather than by algorithm label, which is exactly what makes "these two clusters became one" detectable rather than noise.
- **Technically real:** dynamic and incremental community detection is an established area, not speculation.

### Rung 3 · Federation without centralisation
**The horizon. This is what makes it a Home Ministry system rather than a state system.**

The obstacle to a national criminal network system is not technology. States will not surrender raw crime records to a central pool, for legal, political and practical reasons. Any pitch that assumes a single national database is naive and a knowledgeable judge will say so.

So: each state runs its own instance. Queries propagate between instances. **Only matches return, never raw records.**

- **What it rests on:** you already enforce isolation by rank and district inside the database. Federation across states is the same principle one level up, which is what makes it credible rather than grandiose.
- **Theme fit:** privacy-preserving matching across organisations that do not fully trust each other is precisely the Blockchain and Cybersecurity problem space. This is where your theme placement stops being a stretch and becomes the natural home for the work.
- **The honest hard part:** matching identities across states without exchanging identities. Name it if pressed. Hashed identifier matching and private set intersection are the relevant directions, and saying "this is the hard part and here is the family of techniques" is stronger than pretending it is easy.

### The closer · A system that compounds
Models are currently trained offline and frozen. Every lead an investigator confirms or dismisses is a labelled example that is currently thrown away. Capturing that turns usage into training data, which means the system improves because it is used rather than despite it.

---

## 5. What to CUT or CHANGE in existing material

### From the datathon deck

| Verdict | Item | Reason |
|---|---|---|
| **Cut** | The ten-feature grid | A product catalogue, not an idea. Ten features in five minutes is three seconds each, so nothing lands. Move whole to appendix. |
| **Cut** | The six-category technology slide | Nobody is scored on stack breadth. Reading it aloud costs forty seconds you need for the ladder. |
| **Cut** | The Catalyst services slide, entirely | It existed because a sponsor required it. Here it reads as vendor lock-in on a Home Ministry system. |
| **Cut** | The twelve-box "differs / solves / USP" grid | Three columns of four claims is twelve things, therefore zero things. The two lines on the technical approach slide replace all of it. |
| **Cut** | The 350-word "brief about the solution" paragraph | Unspeakable, and no judge reads while you talk. It becomes the six sentences on slide 2. |
| **Promote** | Multi-jurisdiction offenders | Currently feature five of ten. For MHA it is the most relevant capability you have. |
| **Keep** | The cost slide, folded into slide 6 | Rare and credible. Most teams have no number at all. |
| **Keep** | Two prototype snapshots, one being the graph | Proof it exists. The demo clip does the rest. |
| **Rewire** | The future-development slide | Becomes the vision ladder. Currently four floating items, none resting on anything. |

### From the national run of show

The national version was built to survive a domain expert's scrutiny: validation numbers, published weak results, risk-and-mitigation rows, a traceability table. **Keep all of it for the next round. Do not use it here.** In an internal room that material reads as defensive and eats the time the ladder needs.

Specifically, do not spend time on:
- The precision and recall table. One clause at most if it comes up in Q&A.
- The four-row risks-and-mitigations block. Compressed into the single adoption sentence on slide 6.
- The Built / Proven / Next traceability matrix. Keep it in your pocket for Q&A, not on a slide.

---

## 6. Q&A preparation for this audience

Internal judges probe differently. They will push on reasoning and on whether you personally understand what you built.

**"Why did you pick this problem statement?"**
Very likely, and it is a gift. Answer with the reframe, not with interest: the gap is not data, India digitised years ago, the gap is that networks are organised and records are not. Then note that it is a problem where the analysis has to be defensible, which is a constraint most AI applications do not have and which shaped every decision.

**"How much of this is actually working?"**
Answer plainly and immediately. Deployed, live URL, demo video, and name one thing that is not done. Hesitation here costs more than the gap does.

**"Why not just use ChatGPT on the database?"**
This is the rejected decision, so you have already answered it in the pitch. Repeat it more sharply: a generated query is unverifiable, and in an investigation an unverifiable answer is worse than none. Then give the consequence: we permit no generated queries at all.

**"Where is the blockchain?"**
A distributed ledger solves trust between parties who do not trust each other, which is the wrong shape inside one police force, and bolting one on would be theatre. The property you actually want is tamper-evidence. The audit log is already append-only, and hash-chaining each entry makes it verifiable. Then bridge to rung 3, where cross-state federation genuinely is a trust-between-organisations problem.

**"What did you find hardest?"**
Have one real technical answer ready with the reasoning visible. Good candidates: the district-isolation rules silently switching off inside the streaming chat response because the database setting was transaction-scoped, or getting community alerts to stop re-firing because the clustering algorithm renumbers groups on every run. Both are non-obvious, both show debugging maturity, and both are true.

**"Who did what?"**
Have a one-line answer per person. Internal rounds weight team capability more than national ones do.

**"How is this different from what police already have?"**
CCTNS and ICJS store cases well and connect them badly. You are not replacing the system of record, you sit on top and make what already exists traversable.

---

## 7. Delivery mechanics

- **One speaker, two at most.** Five people rotating through five minutes costs a handover every sixty seconds and reads as a group project rather than a team.
- **Roughly 690 spoken words is the ceiling.** For reference, the "brief about the solution" paragraph in the current deck is about 350 words on its own.
- **Fifteen words maximum visible on any slide.** Slides carry nouns, you carry verbs. If a judge is reading, they are not listening.
- **Record the demo. Never run it live.** Twenty to twenty-five seconds, silent, captioned, embedded in the file. Venue wifi has ended better pitches than yours.
- **Rehearse to 4:30.** You will speak faster on the day and lose ten seconds to setup.
- **Build the appendix.** Everything cut goes after the close: architecture, stack, feature grid, validation numbers, traceability matrix. Flipping to a prepared slide mid-answer reads as depth rather than improvisation.
- **Rehearse the ladder separately.** It is seventy-five seconds of unfamiliar material and it is the part you will fumble first. It is also the part you are being scored on.

---

## 8. Pre-pitch checklist

- [ ] Demo clip recorded, silent, captioned, embedded in the deck file
- [ ] Slide 5 designed as an ascending ladder, not three boxes
- [ ] Appendix slides built from the cut material
- [ ] Speaker assigned, and Q&A responders assigned by topic
- [ ] Timed run at 4:30 or under, twice
- [ ] "What was hardest" answer rehearsed by whoever built that part
- [ ] Cost figure confirmed against the actual bill, and which parts were free tier
- [ ] One-line per-person contribution answer agreed
- [ ] Live deployment checked working the morning of

---

## 9. Open item

The official PS description text for SIH26189 has not been read yet, only the listing row. Once you have it, slide 2 and the solution description should echo its exact vocabulary, since reviewers match your language against the statement they wrote.
