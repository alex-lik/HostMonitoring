"""Daily availability report.

Reads ping results from MySQL, builds an hourly availability chart,
generates a downtime summary and sends both to Telegram.
Designed to run from cron once a day (see ``report.sh``).
"""

from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend for cron/servers

import matplotlib.pyplot as plt
import pandas as pd
import pymysql
import telebot
from yaml import safe_load

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yml"
PLOT_PATH = BASE_DIR / "images" / "availability_plot.png"

DOWN_GAP_MINUTES = 10


def load_db_config(path: Path = CONFIG_PATH) -> dict:
    """Load DB + Telegram settings from YAML config."""
    with path.open("r", encoding="utf-8") as file:
        return (safe_load(file) or {}).get("config", {}) or {}


def fetch_results(db_config: dict, since: datetime) -> list[tuple]:
    """Fetch ``(host, status, datetime)`` rows recorded since ``since``."""
    connection = pymysql.connect(
        host=db_config["host"],
        port=int(db_config.get("port", 3306)),
        user=db_config["user"],
        password=str(db_config["password"]),
        db=db_config["db"],
    )
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT host, status, datetime FROM ping WHERE datetime >= %s",
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            )
            return list(cursor.fetchall())


def to_dataframe(rows: list[tuple]) -> pd.DataFrame:
    """Convert raw DB rows to a DataFrame with an ``hour`` column."""
    df = pd.DataFrame(rows, columns=["host", "status", "datetime"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["hour"] = df["datetime"].dt.hour
    return df


def hourly_availability(df: pd.DataFrame) -> pd.DataFrame:
    """Mean success rate (0-100) per host and hour of day."""
    return (
        df.groupby(["host", "hour"], as_index=False)["status"]
        .mean()
        .assign(availability=lambda t: t["status"] * 100)
        .drop(columns="status")
    )


def plot_availability(df: pd.DataFrame, output: Path = PLOT_PATH) -> Path:
    """Plot hourly availability per host and save to ``output``."""
    availability = hourly_availability(df)
    hosts = df["host"].unique()

    fig, axes = plt.subplots(len(hosts), 1, figsize=(10, 4 * len(hosts)), sharex=True)
    if len(hosts) == 1:
        axes = [axes]

    for ax, host in zip(axes, hosts):
        host_data = availability[availability["host"] == host]
        ax.plot(host_data["hour"], host_data["availability"], marker="o", label=host)
        for _, row in host_data.iterrows():
            ax.text(row["hour"], row["availability"], f'{row["availability"]:.1f}',
                    fontsize=9, ha="right")
        ax.set_ylabel("Availability (%)")
        ax.set_ylim(0, 105)
        ax.set_xticks(range(24))
        ax.legend()
        ax.grid(True)

    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output)
    plt.close(fig)
    return output


def build_report(df: pd.DataFrame, gap_minutes: int = DOWN_GAP_MINUTES) -> str:
    """Build a per-host summary: availability % + downtime intervals."""
    lines: list[str] = []
    for host in df["host"].unique():
        host_data = df[df["host"] == host].sort_values("datetime")
        availability = host_data["status"].mean() * 100
        lines.append(f"IP {host}, доступность {availability:.1f}%")

        if availability < 100:
            downs = host_data.loc[host_data["status"] == 0, "datetime"]
            if not downs.empty:
                start = end = downs.iloc[0]
                for current in downs.iloc[1:]:
                    if (current - end) > pd.Timedelta(minutes=gap_minutes):
                        lines.append(f"Проблемы с доступностью с {start} до {end}")
                        start = current
                    end = current
                lines.append(f"Проблемы с доступностью с {start} до {end}")
    return "\n".join(lines)


def send_to_telegram(message: str, image: Path, db_config: dict) -> None:
    """Send the chart image and the text report to the configured chat."""
    bot = telebot.TeleBot(db_config["telegram_token"])
    chat_id = db_config["chat_id"]
    with image.open("rb") as photo:
        bot.send_photo(chat_id=chat_id, photo=photo)
    bot.send_message(chat_id=chat_id, text=message)


def main() -> None:
    db_config = load_db_config()
    since = datetime.now() - timedelta(days=1)
    rows = fetch_results(db_config, since)
    if not rows:
        return
    df = to_dataframe(rows)
    image = plot_availability(df)
    send_to_telegram(build_report(df), image, db_config)


if __name__ == "__main__":
    main()
