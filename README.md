# HostMonitoring

ICMP availability monitor with MySQL storage and daily Telegram reports.

`monitor.py` pings hosts on a schedule and logs results.
`report.py` aggregates the last 24 hours, renders an hourly availability
chart and sends a downtime summary to Telegram.

## Features

- ICMP polling of a configurable host list
- Parameterized MySQL writes/reads (no string-interpolated SQL)
- Hourly availability chart per host (`matplotlib`, headless `Agg` backend)
- Downtime interval detection with configurable gap merging
- Telegram delivery of chart + text summary
- Cron-ready entry points (`monitor.sh`, `report.sh`)

## Project layout

```text
.
├── monitor.py           # ping hosts -> MySQL
├── report.py            # MySQL -> chart + Telegram report
├── monitor.sh           # venv wrapper for cron (every N minutes)
├── report.sh            # venv wrapper for cron (daily)
├── schema.sql           # `ping` table definition
├── config.yml.example   # example configuration
└── requirements.txt
```

## Requirements

- Python 3.10+
- MySQL 5.7+ / 8.x

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy the example and fill in your values (`config.yml` is git-ignored):

```bash
cp config.yml.example config.yml
```

```yaml
hosts:
  - 8.8.8.8
  - 8.8.4.4
  - 1.1.1.1
config:
  host: 192.168.1.2
  port: 3306
  user: user
  password: password
  db: monitoring
  telegram_token: 0000000000:AAAAAAAAAAAAAAAAAAAA
  chat_id: -00000000
```

## Database

```bash
mysql -u user -p monitoring < schema.sql
```

Table:

```sql
CREATE TABLE IF NOT EXISTS ping (
    host VARCHAR(255) NOT NULL,
    status TINYINT NOT NULL,
    datetime DATETIME NOT NULL
);
```

`status`: `1` = reachable, `0` = unreachable.

## Usage

Run manually:

```bash
./monitor.sh   # ping now
./report.sh    # daily report now
```

Cron example:

```cron
# Ping every 10 minutes
*/10 * * * * /path/to/HostMonitoring/monitor.sh

# Daily report at midnight
0 0 * * * /path/to/HostMonitoring/report.sh
```

## Report example

```text
IP 192.168.0.1, доступность 69.8%
Проблемы с доступностью с 2024-07-21 21:28:05 до 2024-07-21 21:31:02
Проблемы с доступностью с 2024-07-21 21:32:04 до 2024-07-21 21:34:02
IP 192.168.0.2, доступность 100.0%
```

A per-host hourly chart (`images/availability_plot.png`) is sent before the text.
