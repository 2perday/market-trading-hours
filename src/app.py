import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytz
import pandas_market_calendars as mcal
import holidays
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    datefmt="%Y/%m/%d %I:%M:%S %p",
)

EXCHANGES = ["NYSE", "LSE"]
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
STATE_FILE = Path(__file__).parent.parent / "data" / "state.json"
KST = pytz.timezone("Asia/Seoul")
HOLIDAY_PROVIDERS = {"NYSE": holidays.US, "LSE": holidays.GB}

calendar_cache: dict = {}

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("TELEGRAM_TOKEN and CHAT_ID must be set in .env")

bot = Bot(token=TELEGRAM_TOKEN)


@dataclass
class MarketSchedule:
    exchange: str
    open: datetime | None = None
    close: datetime | None = None
    holiday: str | None = None

    @property
    def is_holiday(self) -> bool:
        return self.open is None


def convert_to_kst(dt: datetime) -> str:
    return dt.astimezone(KST).strftime("%H:%M")


def get_market_schedule(exchange: str, current_time: datetime) -> object | None:
    if exchange not in calendar_cache:
        calendar_cache[exchange] = mcal.get_calendar(exchange)
    calendar = calendar_cache[exchange].schedule(
        start_date=current_time, end_date=current_time
    )
    return calendar.iloc[0] if not calendar.empty else None


def get_holiday_name(exchange: str, current_time: datetime) -> str:
    return HOLIDAY_PROVIDERS[exchange]().get(current_time.date(), "Weekend")


def build_schedules(current_time: datetime) -> list[MarketSchedule]:
    result = []
    for exchange in EXCHANGES:
        row = get_market_schedule(exchange, current_time)
        if row is not None:
            result.append(
                MarketSchedule(
                    exchange=exchange,
                    open=row["market_open"],
                    close=row["market_close"],
                )
            )
        else:
            result.append(
                MarketSchedule(
                    exchange=exchange,
                    holiday=get_holiday_name(exchange, current_time),
                )
            )
    return result


def load_state(today: str) -> dict:
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
        if data.get("date") == today:
            logging.info(f"State loaded from file: {data}")
            return data
    return {"date": today, **{ex: {"open": False, "close": False} for ex in EXCHANGES}}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))
    logging.info(f"State updated: {state}")


async def send_notification(message: str) -> None:
    try:
        await bot.send_message(CHAT_ID, text=message)
        logging.info(message)
    except Exception as e:
        logging.error(f"Error sending message: {e}")


async def send_schedule_message(schedules: list[MarketSchedule]) -> None:
    parts = ["🕛 Today's Trading Hours\n"]
    for s in schedules:
        if not s.is_holiday:
            parts.extend(
                [
                    f"#{s.exchange}",
                    f"{convert_to_kst(s.open)} ~ {convert_to_kst(s.close)} KST 🇰🇷\n",
                ]
            )
        else:
            parts.extend([f"#{s.exchange}", f"Market Close\n{s.holiday}\n"])
    await send_notification("\n".join(parts).rstrip())


async def notify_open_close(
    schedules: list[MarketSchedule], state: dict, current_time: datetime
) -> bool:
    current_time_str = current_time.strftime("%H:%M")
    changed = False

    for s in schedules:
        if s.is_holiday:
            continue

        if (
            s.open.strftime("%H:%M") <= current_time_str
            and not state[s.exchange]["open"]
        ):
            await send_notification(f"🟢 #{s.exchange} Market Open")
            state[s.exchange]["open"] = True
            changed = True

        if (
            s.close.strftime("%H:%M") <= current_time_str
            and not state[s.exchange]["close"]
        ):
            await send_notification(f"🔴 #{s.exchange} Market Close")
            state[s.exchange]["close"] = True
            changed = True

    return changed


async def main() -> None:
    current_time = datetime.now(timezone.utc)
    today = current_time.date().isoformat()
    state = load_state(today)
    save_state(state)
    schedules = build_schedules(current_time)
    logging.info(f"Started. date={today}")

    while True:
        current_time = datetime.now(timezone.utc)
        current_date = current_time.date().isoformat()

        if current_date != state["date"]:
            state = {
                "date": current_date,
                **{ex: {"open": False, "close": False} for ex in EXCHANGES},
            }
            schedules = build_schedules(current_time)
            await send_schedule_message(schedules)
            save_state(state)
            logging.info(f"Daily reset: {current_date}")

        changed = await notify_open_close(schedules, state, current_time)
        if changed:
            save_state(state)

        next_minute = current_time.replace(second=0, microsecond=0) + timedelta(
            minutes=1
        )
        sleep_time = (next_minute - datetime.now(timezone.utc)).total_seconds()
        await asyncio.sleep(max(0, sleep_time))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt.")
