CREATE TABLE knowledge_sources (
    source_id TEXT PRIMARY KEY,
    canonical_uri TEXT NOT NULL UNIQUE,
    source_kind TEXT NOT NULL,
    license_spdx TEXT,
    version TEXT,
    content_checksum TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE knowledge_documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES knowledge_sources(source_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    anchor TEXT,
    content_checksum TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, anchor)
);

CREATE TABLE knowledge_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES knowledge_documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK(chunk_index >= 0),
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL CHECK(token_count >= 0),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(document_id, chunk_index)
);

CREATE VIRTUAL TABLE knowledge_chunks_fts USING fts5(
    chunk_id UNINDEXED,
    content,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER knowledge_chunks_fts_insert AFTER INSERT ON knowledge_chunks BEGIN
    INSERT INTO knowledge_chunks_fts(rowid, chunk_id, content)
    VALUES (new.rowid, new.chunk_id, new.content);
END;

CREATE TRIGGER knowledge_chunks_fts_delete AFTER DELETE ON knowledge_chunks BEGIN
    DELETE FROM knowledge_chunks_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER knowledge_chunks_fts_update AFTER UPDATE OF chunk_id, content ON knowledge_chunks BEGIN
    DELETE FROM knowledge_chunks_fts WHERE rowid = old.rowid;
    INSERT INTO knowledge_chunks_fts(rowid, chunk_id, content)
    VALUES (new.rowid, new.chunk_id, new.content);
END;

CREATE TABLE knowledge_edges (
    edge_id TEXT PRIMARY KEY,
    source_ref TEXT NOT NULL,
    relation TEXT NOT NULL,
    target_ref TEXT NOT NULL,
    evidence_ref TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_ref, relation, target_ref, evidence_ref)
);

CREATE TABLE retrieval_traces (
    trace_id TEXT PRIMARY KEY,
    session_id TEXT,
    stage_id TEXT,
    query_checksum TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    candidate_count INTEGER NOT NULL CHECK(candidate_count >= 0),
    packed_token_count INTEGER NOT NULL CHECK(packed_token_count >= 0),
    latency_ms INTEGER NOT NULL CHECK(latency_ms >= 0),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE hardware_samples (
    sample_id TEXT PRIMARY KEY,
    session_id TEXT,
    stage_id TEXT,
    operation TEXT NOT NULL,
    wall_ms INTEGER NOT NULL CHECK(wall_ms >= 0),
    cpu_ms INTEGER NOT NULL CHECK(cpu_ms >= 0),
    peak_rss_bytes INTEGER NOT NULL CHECK(peak_rss_bytes >= 0),
    gpu_ms INTEGER CHECK(gpu_ms IS NULL OR gpu_ms >= 0),
    peak_vram_bytes INTEGER CHECK(peak_vram_bytes IS NULL OR peak_vram_bytes >= 0),
    read_bytes INTEGER CHECK(read_bytes IS NULL OR read_bytes >= 0),
    write_bytes INTEGER CHECK(write_bytes IS NULL OR write_bytes >= 0),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX knowledge_documents_source_idx ON knowledge_documents(source_id);
CREATE INDEX knowledge_chunks_document_idx ON knowledge_chunks(document_id, chunk_index);
CREATE INDEX knowledge_edges_source_idx ON knowledge_edges(source_ref, relation);
CREATE INDEX knowledge_edges_target_idx ON knowledge_edges(target_ref, relation);
CREATE INDEX retrieval_traces_session_idx ON retrieval_traces(session_id, stage_id);
CREATE INDEX hardware_samples_session_idx ON hardware_samples(session_id, stage_id);
