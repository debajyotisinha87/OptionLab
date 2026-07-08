CREATE TABLE IF NOT EXISTS option_data (

    symbol VARCHAR,

    trade_datetime TIMESTAMP,

    trade_date DATE,

    trade_time TIME,

    option_type VARCHAR,

    strike_type VARCHAR,

    expiry_flag VARCHAR,

    expiry_code INTEGER,

    open DOUBLE,

    high DOUBLE,

    low DOUBLE,

    close DOUBLE,

    volume BIGINT,

    oi BIGINT,

    iv DOUBLE,

    spot DOUBLE
);
