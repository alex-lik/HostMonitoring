CREATE TABLE IF NOT EXISTS ping (
    host VARCHAR(255) NOT NULL,
    status TINYINT NOT NULL,
    datetime DATETIME NOT NULL,
    KEY idx_ping_datetime (datetime),
    KEY idx_ping_host (host)
);
