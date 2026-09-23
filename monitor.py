"""Host availability monitor.

Pings hosts listed in ``config.yml`` and stores the results in MySQL.
Designed to run from cron every N minutes (see ``monitor.sh``).
"""

from pathlib import Path

import pymysql
from ping3 import ping
from yaml import safe_load

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yml"

PING_TIMEOUT = 2  # seconds


def load_config(path: Path = CONFIG_PATH) -> tuple[list[str], dict]:
    """Load monitored hosts and DB settings from YAML config."""
    with path.open("r", encoding="utf-8") as file:
        raw = safe_load(file) or {}
    hosts = raw.get("hosts", []) or []
    db_config = raw.get("config", {}) or {}
    return list(hosts), dict(db_config)


def check_hosts(hosts: list[str], timeout: float = PING_TIMEOUT) -> dict[str, int]:
    """Ping each host. Returns ``{host: 1}`` on success, ``{host: 0}`` otherwise."""
    results: dict[str, int] = {}
    for host in hosts:
        try:
            results[host] = 1 if ping(host, timeout=timeout) else 0
        except Exception:
            results[host] = 0
    return results


def save_results(results: dict[str, int], db_config: dict) -> None:
    """Insert ping results into the ``ping`` table using a parameterized query."""
    if not results:
        return
    connection = pymysql.connect(
        host=db_config["host"],
        port=int(db_config.get("port", 3306)),
        user=db_config["user"],
        password=str(db_config["password"]),
        db=db_config["db"],
    )
    rows = [(host, status) for host, status in results.items()]
    with connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO ping (host, status, datetime) VALUES (%s, %s, NOW())",
                rows,
            )
        connection.commit()


def main() -> None:
    hosts, db_config = load_config()
    if not hosts:
        return
    results = check_hosts(hosts)
    save_results(results, db_config)


if __name__ == "__main__":
    main()
