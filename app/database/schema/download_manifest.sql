CREATE TABLE IF NOT EXISTS download_manifest (

    job_id VARCHAR NOT NULL,

    batch_number INTEGER NOT NULL,

    underlying VARCHAR NOT NULL,

    instrument VARCHAR NOT NULL,

    expiry_type VARCHAR NOT NULL,

    option_type VARCHAR NOT NULL,

    strike_offset INTEGER NOT NULL,

    interval INTEGER NOT NULL,

    from_date DATE NOT NULL,

    to_date DATE NOT NULL,

    expected_rows INTEGER,

    downloaded_rows INTEGER DEFAULT 0,

    inserted_rows INTEGER DEFAULT 0,

    duplicate_rows INTEGER DEFAULT 0,

    retry_count INTEGER DEFAULT 0,

    checksum VARCHAR,

    status VARCHAR NOT NULL,

    started_at TIMESTAMP,

    completed_at TIMESTAMP,

    error_message VARCHAR
);