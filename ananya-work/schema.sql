CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

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
    sex_ratio               INT,
    composite_stress_index  NUMERIC,
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

CREATE TABLE person (
    person_id             TEXT PRIMARY KEY,
    canonical_person_id   TEXT REFERENCES person(person_id),
    name                  TEXT NOT NULL,
    age                   INT,
    sex                   TEXT,
    district_id           TEXT REFERENCES district(district_id),
    address_text          TEXT,
    created_at            TIMESTAMP DEFAULT now()
);

CREATE TABLE person_match_candidate (
    id              SERIAL PRIMARY KEY,
    person_a_id     TEXT REFERENCES person(person_id),
    person_b_id     TEXT REFERENCES person(person_id),
    match_score     NUMERIC,
    match_method    TEXT,
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
    status          TEXT
);

CREATE TABLE offense (
    offense_id        TEXT PRIMARY KEY,
    incident_id       TEXT REFERENCES incident(incident_id),
    crime_head        TEXT NOT NULL,
    mo_text           TEXT,
    mo_signature      TEXT,
    severity_weight   NUMERIC
);

CREATE TABLE case_person_role (
    incident_id   TEXT REFERENCES incident(incident_id),
    person_id     TEXT REFERENCES person(person_id),
    role          TEXT NOT NULL,
    PRIMARY KEY (incident_id, person_id, role)
);

CREATE TABLE financial_transaction (
    transaction_id      TEXT PRIMARY KEY,
    from_account         TEXT,
    to_account            TEXT,
    amount                NUMERIC,
    tx_date               DATE,
    linked_person_id      TEXT REFERENCES person(person_id),
    synthetic_pattern     TEXT
);

CREATE TABLE mo_linkage_series (
    series_id                  TEXT,
    incident_id                TEXT REFERENCES incident(incident_id),
    offense_id                 TEXT REFERENCES offense(offense_id),
    true_offender_person_id    TEXT REFERENCES person(person_id),
    PRIMARY KEY (series_id, incident_id)
);

CREATE TABLE mo_linkage_cluster (
    id                 SERIAL PRIMARY KEY,
    offense_id         TEXT REFERENCES offense(offense_id),
    cluster_id         TEXT,
    similarity_score   NUMERIC,
    model_version      TEXT NOT NULL,
    computed_at        TIMESTAMP DEFAULT now()
);

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

CREATE TABLE predicted_link (
    id               SERIAL PRIMARY KEY,
    person_id_a      TEXT REFERENCES person(person_id),
    person_id_b      TEXT REFERENCES person(person_id),
    confidence       NUMERIC,
    source_tool      TEXT,
    evidence         TEXT,
    model_version    TEXT,
    computed_at      TIMESTAMP DEFAULT now()
);

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

CREATE TABLE district_composite_index (
    id               SERIAL PRIMARY KEY,
    district_id      TEXT REFERENCES district(district_id),
    year             INT NOT NULL,
    method           TEXT NOT NULL,
    composite_value  NUMERIC NOT NULL,
    computed_at      TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_district_composite_index_district ON district_composite_index (district_id, year, computed_at DESC);

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
    chunk_type     TEXT,
    chunk_text     TEXT,
    embedding      VECTOR(384)
);

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
CREATE INDEX idx_person_name_trgm ON person USING gin (name gin_trgm_ops);
CREATE INDEX idx_narrative_chunk_embedding ON narrative_chunk USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);