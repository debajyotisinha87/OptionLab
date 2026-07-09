CREATE TABLE IF NOT EXISTS download_jobs (

    job_id VARCHAR PRIMARY KEY,

    underlying VARCHAR NOT NULL,

    instrument VARCHAR NOT NULL,

    expiry_type VARCHAR NOT NULL,

    option_types VARCHAR NOT NULL,

    strike_from INTEGER NOT NULL,

    strike_to INTEGER NOT NULL,

    interval INTEGER NOT NULL,

    start_date DATE NOT NULL,

    end_date DATE NOT NULL,

    status VARCHAR NOT NULL,

    created_at TIMESTAMP NOT NULL,

    started_at TIMESTAMP,

    completed_at TIMESTAMP,

    total_batches INTEGER DEFAULT 0,

    completed_batches INTEGER DEFAULT 0,

    failed_batches INTEGER DEFAULT 0,

    total_rows BIGINT DEFAULT 0,

    parquet_output_dir VARCHAR,

    remarks VARCHAR
);