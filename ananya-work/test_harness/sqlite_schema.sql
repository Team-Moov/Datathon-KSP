-- SQLite subset of schema.sql, for offline testing without Postgres.
-- Covers: data loading, graph_features, mo_linkage, lead_rec, risk_score.
-- Deliberately excludes: pgvector/narrative_chunk (no SQLite equivalent),
-- person_match_candidate, document (not touched by these 4 scripts).
-- This is NOT a replacement for schema.sql -- run the real one against
-- Postgres before anything goes near production.

CREATE TABLE district (
    district_id     TEXT PRIMARY KEY,
    district_name   TEXT NOT NULL
);

CREATE TABLE district_socioeconomic (
    district_id             TEXT,
    year                    INT,
    literacy_pct            NUMERIC,
    unemployment_pct        NUMERIC,
    urbanization_pct        NUMERIC,
    sex_ratio               INT,
    composite_stress_index  NUMERIC,
    PRIMARY KEY (district_id, year)
);

CREATE TABLE crime_stat_aggregate (
    district_id  TEXT,
    year         INT,
    crime_head   TEXT,
    count        INT
);

CREATE TABLE person (
    person_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    age             INT,
    sex             TEXT,
    district_id     TEXT,
    address_text    TEXT
);

CREATE TABLE incident (
    incident_id     TEXT PRIMARY KEY,
    fir_number      TEXT,
    district_id     TEXT,
    date_occurred   DATE NOT NULL,
    date_reported   DATE,
    status          TEXT
);

CREATE TABLE offense (
    offense_id        TEXT PRIMARY KEY,
    incident_id       TEXT,
    crime_head        TEXT NOT NULL,
    mo_text           TEXT,
    mo_signature      TEXT,
    severity_weight   NUMERIC
);

CREATE TABLE case_person_role (
    incident_id   TEXT,
    person_id     TEXT,
    role          TEXT NOT NULL,
    PRIMARY KEY (incident_id, person_id, role)
);

CREATE TABLE financial_transaction (
    transaction_id      TEXT PRIMARY KEY,
    from_account         TEXT,
    to_account            TEXT,
    amount                NUMERIC,
    tx_date               DATE,
    linked_person_id      TEXT,
    synthetic_pattern     TEXT
);

CREATE TABLE mo_linkage_series (
    series_id                  TEXT,
    incident_id                TEXT,
    offense_id                 TEXT,
    true_offender_person_id    TEXT,
    PRIMARY KEY (series_id, incident_id)
);

CREATE TABLE mo_linkage_cluster (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    offense_id         TEXT,
    cluster_id         TEXT,
    similarity_score   NUMERIC,
    model_version      TEXT NOT NULL,
    computed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE person_graph_metric (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id       TEXT,
    pagerank        NUMERIC,
    betweenness     NUMERIC,
    community_id    TEXT,
    graph_version   TEXT NOT NULL,
    computed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE risk_score (
    id                            INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id                     TEXT,
    model_version                 TEXT NOT NULL,
    score                         NUMERIC NOT NULL,
    severity_history_component    NUMERIC,
    centrality_component          NUMERIC,
    mo_consistency_component      NUMERIC,
    associate_risk_component      NUMERIC,
    computed_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    human_reviewed                BOOLEAN DEFAULT 0
);

CREATE TABLE predicted_link (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id_a      TEXT,
    person_id_b      TEXT,
    confidence       NUMERIC,
    source_tool      TEXT,
    evidence         TEXT,
    model_version    TEXT,
    computed_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);