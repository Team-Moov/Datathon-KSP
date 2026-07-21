-- ============================================================================
-- Crime portal poly-store: relational layer
-- ============================================================================
-- This is the "boring gray boxes" layer from the pipeline design: Incident,
-- Offense, Person, Case_Person_Role, plus the derived/versioned tables that
-- the network, risk, and lead-recommendation features write into.
--
-- Design rules encoded here, not just described in prose:
--   1. Derived outputs (risk_score, predicted_link, mo_linkage_cluster) are
--      APPEND-ONLY. No UPDATEs to a score/prediction row, ever -- a new
--      computation is a new row with its own model_version and timestamp.
--      This is what lets an investigator see "this person's risk score rose
--      over 6 months and exactly why."
--   2. mo_linkage_series (ground truth, used to TRAIN the model) is a
--      completely separate table from mo_linkage_cluster (the model's
--      versioned OUTPUT). Never conflate a label with a prediction.
--   3. Sensitive fields (religion/caste) are deliberately NOT modeled in
--      this schema at all for this build. If a real deployment needs them,
--      they belong in a separate person_sensitive table behind row-level
--      security -- never as columns on `person`, never joined into any
--      feature-building query by default.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- trigram similarity, used for entity-resolution blocking/fuzzy match

-- ----------------------------------------------------------------------------
-- Reference / dimension tables
-- ----------------------------------------------------------------------------

CREATE TABLE district (
    district_id     TEXT PRIMARY KEY,
    district_name   TEXT NOT NULL
);

CREATE TABLE district_socioeconomic (
    district_id             TEXT REFERENCES district(district_id),
    year                    INT NOT NULL,
    literacy_pct            NUMERIC,
    unemployment_pct        NUMERIC,
    urbanization_pct        NUMERIC,
    sex_ratio                INT,
    composite_stress_index  NUMERIC,      -- versioned by (district_id, year); recompute as a new year row, don't overwrite
    computed_at             TIMESTAMP DEFAULT now(),
    PRIMARY KEY (district_id, year)
);

CREATE TABLE crime_stat_aggregate (
    district_id  TEXT REFERENCES district(district_id),
    year         INT NOT NULL,
    crime_head   TEXT NOT NULL,
    count        INT NOT NULL,
    PRIMARY KEY (district_id, year, crime_head)
);

-- ----------------------------------------------------------------------------
-- Core entities
-- ----------------------------------------------------------------------------

CREATE TABLE person (
    person_id             TEXT PRIMARY KEY,
    canonical_person_id   TEXT REFERENCES person(person_id),  -- entity-resolution merge target; NULL = this row IS canonical
    name                  TEXT NOT NULL,
    age                   INT,
    sex                   TEXT,
    district_id           TEXT REFERENCES district(district_id),
    address_text          TEXT,
    created_at            TIMESTAMP DEFAULT now()
);

-- entity-resolution candidate merges live here, reviewed before they affect canonical_person_id
CREATE TABLE person_match_candidate (
    id              SERIAL PRIMARY KEY,
    person_id_a     TEXT REFERENCES person(person_id),
    person_id_b     TEXT REFERENCES person(person_id),
    match_score     NUMERIC,
    match_method    TEXT,            -- e.g. 'fuzzy_name_address_v1'
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','confirmed','rejected')),
    reviewed_by     TEXT,
    reviewed_at     TIMESTAMP,
    created_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE incident (
    incident_id     TEXT PRIMARY KEY,
    fir_number      TEXT,
    district_id     TEXT REFERENCES district(district_id),
    date_occurred   DATE NOT NULL,
    date_reported   DATE,
    status          TEXT,
    source_type     TEXT DEFAULT 'synthetic'
);

CREATE TABLE offense (
    offense_id        TEXT PRIMARY KEY,
    incident_id       TEXT REFERENCES incident(incident_id),
    crime_head        TEXT NOT NULL,
    mo_text           TEXT,
    mo_signature      TEXT,
    severity_weight   NUMERIC,        -- CHI-style; see reference/chi_severity_weights.csv for provenance
    weapon_used       TEXT
);

CREATE TABLE case_person_role (
    incident_id   TEXT REFERENCES incident(incident_id),
    person_id     TEXT REFERENCES person(person_id),
    role          TEXT NOT NULL,       -- accused | victim | witness | complainant
    PRIMARY KEY (incident_id, person_id, role)
);

CREATE TABLE financial_transaction (
    transaction_id      TEXT PRIMARY KEY,
    from_account         TEXT,
    to_account            TEXT,
    amount                NUMERIC,
    tx_date               DATE,
    linked_person_id      TEXT REFERENCES person(person_id),
    synthetic_pattern     TEXT          -- demo-only ground-truth tag; drop this column on real data
);

-- ----------------------------------------------------------------------------
-- MO linkage: ground truth (training labels) vs. model output (versioned)
-- ----------------------------------------------------------------------------

CREATE TABLE mo_linkage_series (
    series_id                  TEXT,
    incident_id                TEXT REFERENCES incident(incident_id),
    offense_id                 TEXT REFERENCES offense(offense_id),
    true_offender_person_id    TEXT REFERENCES person(person_id),
    PRIMARY KEY (series_id, incident_id)
);
-- ^ TRAINING LABELS ONLY. Never read by the serving path -- the model's
-- actual predictions live in mo_linkage_cluster below.

CREATE TABLE mo_linkage_cluster (
    id                 SERIAL PRIMARY KEY,
    offense_id         TEXT REFERENCES offense(offense_id),
    cluster_id         TEXT,
    similarity_score   NUMERIC,
    model_version      TEXT NOT NULL,
    computed_at        TIMESTAMP DEFAULT now()
);
-- ^ MODEL OUTPUT, append-only.

-- ----------------------------------------------------------------------------
-- Derived / versioned outputs consumed by the dashboard
-- ----------------------------------------------------------------------------

CREATE TABLE risk_score (
    id                            SERIAL PRIMARY KEY,
    person_id                     TEXT REFERENCES person(person_id),
    model_version                 TEXT NOT NULL,
    score                         NUMERIC NOT NULL,
    severity_history_component    NUMERIC,
    centrality_component          NUMERIC,
    mo_consistency_component      NUMERIC,
    associate_risk_component      NUMERIC,
    computed_at                   TIMESTAMP DEFAULT now(),
    human_reviewed                BOOLEAN DEFAULT FALSE
);
-- ^ append-only: a new row per computation, never an UPDATE to an old score.

CREATE TABLE predicted_link (
    id               SERIAL PRIMARY KEY,
    person_id_a      TEXT REFERENCES person(person_id),
    person_id_b      TEXT REFERENCES person(person_id),
    confidence       NUMERIC,
    source_tool      TEXT,        -- e.g. 'node2vec_logreg_v1'
    evidence         TEXT,        -- human-readable "why": shared associate, financial link, MO-cluster overlap
    model_version    TEXT,
    computed_at      TIMESTAMP DEFAULT now()
);
-- ^ never rendered identically to a confirmed case_person_role co-accusal --
-- that distinction belongs to the application layer, not this table, but
-- keeping predicted_link physically separate from case_person_role is what
-- makes that distinction enforceable at all.

-- ----------------------------------------------------------------------------
-- Graph-derived metrics (community + centrality), versioned
-- ----------------------------------------------------------------------------
-- Written by ml/features/graph_features.py. Append-only, same pattern as
-- risk_score and mo_linkage_cluster: one row per person per graph
-- computation run, never an UPDATE to a prior run. graph_version
-- distinguishes runs (e.g. includes the as_of_date cutoff used, so a
-- temporal snapshot run and a "full graph" run are both traceable).
-- Originally added in migrations/001_person_graph_metric.sql; folded in
-- here once it became part of the base build.

CREATE TABLE person_graph_metric (
    id              SERIAL PRIMARY KEY,
    person_id       TEXT REFERENCES person(person_id),
    pagerank        NUMERIC,
    betweenness     NUMERIC,
    community_id    TEXT,
    graph_version   TEXT NOT NULL,
    computed_at     TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_person_graph_metric_person ON person_graph_metric (person_id, computed_at DESC);
CREATE INDEX idx_person_graph_metric_version ON person_graph_metric (graph_version);

-- ----------------------------------------------------------------------------
-- District composite index, versioned
-- ----------------------------------------------------------------------------
-- Written by sociological/composite_index.py. Kept separate from
-- district_socioeconomic.composite_stress_index (which is baked into the
-- synthetic generator's output) so this can be recomputed independently
-- once real NDAP indicators replace the placeholder, without touching the
-- generator. Same append-only pattern as risk_score / mo_linkage_cluster.

CREATE TABLE district_composite_index (
    id               SERIAL PRIMARY KEY,
    district_id      TEXT REFERENCES district(district_id),
    year             INT NOT NULL,
    method           TEXT NOT NULL,      -- 'percentile_rank' | 'pca'
    composite_value  NUMERIC NOT NULL,
    computed_at      TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_district_composite_index_district ON district_composite_index (district_id, year, computed_at DESC);

-- ----------------------------------------------------------------------------
-- Provenance + vector layer
-- ----------------------------------------------------------------------------

CREATE TABLE document (
    document_id           TEXT PRIMARY KEY,
    source_type            TEXT,
    file_format             TEXT,
    linked_incident_id      TEXT REFERENCES incident(incident_id),
    extraction_method        TEXT,
    confidence_score          NUMERIC,
    raw_file_ref               TEXT,
    human_verified              BOOLEAN DEFAULT FALSE,
    ingested_at                  TIMESTAMP DEFAULT now()
);

CREATE TABLE narrative_chunk (
    chunk_id       SERIAL PRIMARY KEY,
    document_id    TEXT REFERENCES document(document_id),
    incident_id    TEXT REFERENCES incident(incident_id),
    chunk_type     TEXT,             -- 'mo_gist' | 'statement' | 'news'
    chunk_text     TEXT,
    embedding      VECTOR(384)       -- dimension matches whatever sentence-embedding model you pick
);

-- ----------------------------------------------------------------------------
-- Indexes -- these matter once you're past a few thousand rows
-- ----------------------------------------------------------------------------

CREATE INDEX idx_incident_district_date ON incident (district_id, date_occurred);
CREATE INDEX idx_offense_incident ON offense (incident_id);
CREATE INDEX idx_offense_crime_head ON offense (crime_head);
CREATE INDEX idx_cpr_person ON case_person_role (person_id);
CREATE INDEX idx_cpr_incident ON case_person_role (incident_id);
CREATE INDEX idx_fintx_from ON financial_transaction (from_account);
CREATE INDEX idx_fintx_to ON financial_transaction (to_account);
CREATE INDEX idx_risk_score_person ON risk_score (person_id, computed_at DESC);
CREATE INDEX idx_predicted_link_a ON predicted_link (person_id_a);
CREATE INDEX idx_predicted_link_b ON predicted_link (person_id_b);
CREATE INDEX idx_mo_cluster_offense ON mo_linkage_cluster (offense_id);
CREATE INDEX idx_person_name_trgm ON person USING gin (name gin_trgm_ops);   -- fuzzy-match blocking for entity resolution
CREATE INDEX idx_narrative_chunk_embedding ON narrative_chunk USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
