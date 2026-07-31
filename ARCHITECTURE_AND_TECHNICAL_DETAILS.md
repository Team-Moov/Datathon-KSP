# Karnataka Crime Analytics Platform – Architecture & Technical Details

This document provides a comprehensive deep-dive into the architecture, design choices, data models, and specialized analytics components of the Karnataka Crime Analytics Platform.

## 1. System Overview

The Karnataka Crime Analytics Platform is an advanced investigative and analytical toolset for the Karnataka Police. It bridges the gap between structured relational data (FIRs, chargesheets, officer roles), highly interconnected entity networks (organized crime, financial flows), and unstructured narrative data (statements, document text). 

It features an intelligent conversational AI (Gemini-backed) that acts as an orchestration agent, utilizing deterministic analytical tools to ground its answers in verifiable facts, enforcing a strict division between data computation and AI narration.

## 2. Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **ORM**: SQLAlchemy 2.0 (Async) + Alembic for migrations
- **Databases**:
  - **Relational**: PostgreSQL + `asyncpg`
  - **Vector**: pgvector (for semantic search and embedding storage)
  - **Graph**: Neo4j (async driver) for network analysis (co-offending, financial layers)
  - **Cache/Broker**: Redis (used for caching, Celery broker, and Celery results backend)
- **Background Jobs**: Celery (for analytics recalculation, document processing)
- **AI/ML**: Vertex AI Gemini API (Agent orchestration, chat, NER, extraction)

### Frontend
- **Framework**: React 19 + TypeScript + Vite
- **Routing**: React Router
- **Styling**: Tailwind CSS + Radix UI (shadcn/ui-like component base)
- **State/Query Management**: React Query (TanStack Query)
- **Mapping**: Leaflet + React Leaflet
- **Data Visualization**: Recharts, D3-force (for network graphs). Includes components for temporal trends, socio-correlation matrices, and victim demographics.
- **Internationalization (i18n)**: `i18next` and `react-i18next` (Supports English, Hindi, and Kannada).

### Deployment & Orchestration
- Docker & Docker Compose (Frontend, API, Postgres, Neo4j, Redis, Celery Workers)
- Nginx (for serving the built frontend)

## 3. Data Architecture (Poly-store Approach)

The system embraces a polyglot persistence strategy, mapping specific types of data to the engines best suited to query them:

### 3.1 Relational Store (PostgreSQL)
Acts as the source of truth for structured entity data, RBAC, and audit logs.
- **Core Entities**: `CaseMaster`, `Person`, `Document`, `FinancialTransaction`, `Alert`.
- **Security**: Utilizes Postgres Row-Level Security (RLS) to enforce district-level data isolation directly at the database engine level.

### 3.2 Graph Store (Neo4j)
Used strictly for relationship traversal and network-based typologies, avoiding complex and slow recursive SQL joins.
- **Nodes**: `Person`, `Incident`, `Account`.
- **Edges**: `ACCUSED_IN`, `VICTIM_IN`, `WITNESSED`, `ASSOCIATED_WITH`, `TRANSACTED_WITH`, `PREDICTED_LINK`.
- **Key Use Cases**: Ego networks, multi-jurisdiction offender detection, layering cycles in financial crime, and Louvain community detection.

### 3.3 Vector Store (pgvector)
Used for semantic search and narrative chunking.
- **Model**: `VectorChunk` stores narrative text blocks with a 384-dimensional embedding (generated via Vertex AI `text-embedding-005`).
- **Index**: Uses `ivfflat` or HNSW for fast nearest-neighbor lookups.

## 4. Security, Governance, and RBAC

The platform enforces a capability-based Role-Based Access Control (RBAC) model combined with Row-Level Security (RLS).

### 4.1 Role Tiers
The system defines granular capabilities rather than a simple linear hierarchy, as specialist roles (Analysts, Policy Makers) require cross-cutting access:
- **CONSTABLE**: Basic case viewing, hotspot trends.
- **INSPECTOR**: Sensitive case viewing, unmasked PII, basic ego networks, AI case briefing.
- **DSP / SP**: Case editing, document promotion, advanced network views, risk scoring, financial crime data, sharing capabilities.
- **CRIME_ANALYST**: Specialist data-steward role; manages analytics jobs, runs GWR.
- **POLICY_MAKER**: Aggregate-only access (ecological-fallacy wall); views trends and hotspots but blocked from individual case PII or networks.
- **DGP**: Full system visibility + user management.

### 4.2 Row-Level Security (RLS)
The FastAPI app establishes two SQLAlchemy engines:
1. **Admin Engine**: Connects as Postgres superuser for DDL (migrations, table creation).
2. **Runtime Engine**: Connects as a restricted `app_runtime` role. 
Before any query, the backend sets session variables (`app.current_role`, `app.current_district_id`). The Postgres RLS policies automatically filter out `case_master` and `person_case_role` rows that do not belong to the user's district (unless they possess a state-wide role like DSP or DGP).

## 5. Analytics & Machine Learning Modules

The system includes multiple deterministic analytics engines, separating the hard computation from the LLM's narration.

### 5.1 Criminal Network Analysis
- **Engine**: NetworkX & Neo4j.
- **Features**:
  - Ego network expansion.
  - PageRank and Betweenness Centrality for identifying gang leaders and brokers.
  - Louvain Community Detection (run via NetworkX on the co-offending bipartite projection) to identify organized crime syndicates.
  - Link Prediction: Surfaces plausible, unconfirmed edges based on shared attributes/co-offending patterns.

### 5.2 Hawkes / ETAS Spatio-Temporal Forecasting
- **Purpose**: Predictive policing and hotspot forecasting.
- **Mechanism**: Models crime as a self-exciting point process where past crimes temporarily increase the probability of future nearby crimes (near-repeat victimization).
- **Covariates**: Integrates district-level socio-economic stress indices (e.g., unemployment, literacy) as a baseline rate modifier (Feed-forward integration).

### 5.3 Financial Crime Detection
- **Structuring (Smurfing)**: Detects repeated sub-threshold (e.g., < 1M INR) transfers between the same source and destination within a rolling 7-day window.
- **Funnel/Mule Accounts**: Detects sudden bursts of multi-source deposits into previously dormant accounts, followed by immediate, near-total withdrawals.
- **Layering Cycles**: Uses Neo4j path finding (`MATCH path = (a)-[:TRANSACTED_WITH*2..6]->(a)`) to find circular money movement.
- **Organized Clusters**: Runs Louvain community detection specifically over accounts previously flagged for suspicious activity.

### 5.4 Risk Profiling
- Generates a composite risk score for individuals based on their criminal history (severity weights), centrality in the network (PageRank), MO consistency, and the risk levels of their known associates.

### 5.5 Geographically Weighted Regression (GWR)
- **Purpose**: Correlates socio-economic factors (literacy, unemployment, urbanization) against Crime Harm Index (CHI)-weighted crime totals.
- **Execution**: Runs as a batch Celery job using the `mgwr` Python library. It calculates local coefficients for every district (using district centroids as spatial coordinates), allowing analysts to see how the drivers of crime vary geographically across the state.

### 5.6 Temporal & Seasonal Crime-Pattern Analytics
- **Purpose**: Analyzes crime occurrences across different temporal dimensions (hour-of-day, day-of-week, monthly seasonality).
- **Execution**: Aggregates `CaseMaster` data dynamically to calculate crime occurrence percentages, filtering by district and crime type. Exposes coverage percentages to ensure investigators are aware of data completeness (e.g., cases without recorded incident times).

## 6. Conversational AI Orchestration (Gemini LangGraph-style)

The core investigative interface is a conversational agent powered by Vertex AI's Gemini (`gemini-2.5-flash`).

### 6.1 Tool-Calling Loop
Instead of generating generic advice, the AI acts as a router:
1. User asks a question (e.g., "Who are the leaders of the organized group in district 3?").
2. The AI decides which deterministic tools to call (e.g., `get_graph_subset` followed by `compute_centrality`).
3. The backend executes the Python tool and appends the raw JSON result into the conversation context.
4. The loop repeats until the AI has all necessary data (up to 6 rounds).
5. The AI generates a final narrated response *strictly grounded* in the JSON data it just retrieved.

### 6.2 Deterministic UI Widgets
When a tool returns complex data (e.g., a network graph, a hotspot map, a financial flow), the backend emits a `widget` event over the Server-Sent Events (SSE) stream. The frontend catches this and renders an interactive React component inline with the chat, alongside the text narration.

### 6.3 Grounding & Hallucination Prevention
- The system prompt explicitly forbids the AI from guessing statistics, UUIDs, or relationships.
- All "heavy lifting" (math, graph traversal, spatial forecasting) is executed by deterministic Python code, never the LLM. The LLM's only job is to route intent and summarize the verifiable output.

## 7. Data Ingestion Pipeline

The ingestion service (`app.services.ingestion_service.py`) handles raw files (FIRs, Chargesheets, Bank Statements) in a 5-step process:
1. **Classification**: Identifies the document type and format.
2. **Extraction**: Uses specialized extractors (e.g., `FinancialCsvExtractor`, Zia OCR for PDFs) to pull structured data and narrative text.
3. **Entity Resolution**: Matches extracted names/entities against the existing Postgres database to prevent duplicate entity creation.
4. **Poly-store Load**: 
   - Inserts relational records (Cases, Persons, Transactions) into Postgres.
   - Embeds narrative text via Vertex AI and stores it in pgvector.
   - Syncs new entities and edges to Neo4j via the `GraphSyncService`.
5. **Audit**: Logs the ingestion event with provenance tracking.

## 8. Asynchronous Processing (Celery)

Celery manages heavy offline analytics tasks, keeping the API responsive:
- **`run_gwr_analysis_task`**: Recomputes the Geographically Weighted Regression model across all districts.
- **`update_risk_scores_task`**: Recalculates person risk scores based on new case data.
- **`detect_mo_linkages_task`**: Finds similar crimes (series) based on Jaccard similarity of Modus Operandi (MO) features.
- **`sync_neo4j_graph_task`**: Bulk-syncs Postgres relational data into the Neo4j graph format for consistency.
