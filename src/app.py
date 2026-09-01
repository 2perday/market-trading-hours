import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

import pytz
import pandas_market_calendars as mcal
import holidays
from telegram import Bot
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.DEBUG,
    datefmt="%Y/%m/%d %I:%M:%S %p",
)

exchanges = ["NYSE", "LSE"]

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# 전역 timezone 객체
KST = pytz.timezone("Asia/Seoul")
EST = pytz.timezone("America/New_York")

# 캘린더 캐시
calendar_cache = {}

bot = Bot(token=TELEGRAM_TOKEN)


def convert_to_kst(current_time):
    return current_time.astimezone(KST).strftime("%H:%M")


def convert_to_est(current_time):
    return current_time.astimezone(EST).strftime("%H:%M")


def check_est_edt(current_time):
    return current_time.astimezone(EST).strftime("%Z")


async def get_market_schedule(exchange, current_time):
    if exchange not in calendar_cache:
        calendar_cache[exchange] = mcal.get_calendar(exchange)

    market = calendar_cache[exchange]
    calendar = market.schedule(start_date=current_time, end_date=current_time)

    if not calendar.empty:
        return calendar.iloc[0]
    else:
        return None


async def get_market_holidays(exchange, current_time):
    if exchange == "LSE":
        market_holidays = holidays.GB()
    elif exchange == "NYSE":
        market_holidays = holidays.US()

    if current_time in market_holidays:
        return market_holidays[current_time]
    else:
        return "Weekend"


async def update_schedules(list_schedule, current_time):
    list_schedule.clear()

    for exchange in exchanges:
        schedule = await get_market_schedule(exchange, current_time)

        if schedule is not None:
            list_schedule.append(
                {
                    "exchange": exchange,
                    "open": schedule["market_open"],
                    "close": schedule["market_close"],
                }
            )
        else:
            list_schedule.append({"exchange": exchange, "holiday?": 1})


async def send_schedule_message(list_schedule, current_time):
    message_parts = ["🕛 Today's Trading Hours\n"]

    for schedule in list_schedule:
        if "holiday?" not in schedule or schedule["holiday?"] != 1:
            open_time_kst = convert_to_kst(schedule["open"])
            close_time_kst = convert_to_kst(schedule["close"])

            message_parts.extend(
                [
                    f"#{schedule['exchange']}",
                    f"{open_time_kst} ~ {close_time_kst} KST 🇰🇷\n",
                ]
            )
        else:
            holiday_message = await get_market_holidays(
                schedule["exchange"], current_time
            )
            message_parts.extend(
                [f"#{schedule['exchange']}", f"Market Close\n{holiday_message}\n"]
            )

    processed_message = "\n".join(message_parts).rstrip()
    await send_notification(CHAT_ID, processed_message)


async def notify_market_open_or_close(list_schedule, message_sent, current_time):
    current_time_str = current_time.strftime("%H:%M")

    for schedule in list_schedule:
        if "open" in schedule and "close" in schedule:
            if (
                schedule["open"].strftime("%H:%M") <= current_time_str
            ) and not message_sent[schedule["exchange"]]["open"]:
                await send_notification(
                    CHAT_ID, f"🟢 #{schedule['exchange']} Market Open"
                )
                message_sent[schedule["exchange"]]["open"] = True

            elif (
                schedule["close"].strftime("%H:%M") <= current_time_str
            ) and not message_sent[schedule["exchange"]]["close"]:
                await send_notification(
                    CHAT_ID, f"🔴 #{schedule['exchange']} Market Close"
                )
                message_sent[schedule["exchange"]]["close"] = True


async def send_notification(CHAT_ID, message):
    try:
        await bot.send_message(CHAT_ID, text=message)
        logging.info(f"{message}")
    except Exception as e:
        logging.error(f"Error sending message: {e}")


async def main():
    last_update = None
    list_schedule = []
    message_sent = {exchange: {"open": False, "close": False} for exchange in exchanges}

    await update_schedules(list_schedule, datetime.now(timezone.utc))
    logging.info(f"reset at {datetime.now()}.")
    while True:
        current_time = datetime.now(timezone.utc)

        if (current_time.hour == 0 and current_time.minute == 0) and (
            last_update is None or current_time.date() > last_update.date()
        ):
            await update_schedules(list_schedule, current_time)
            await send_schedule_message(list_schedule, current_time)
            message_sent = {
                exchange: {"open": False, "close": False} for exchange in exchanges
            }
            last_update = current_time
            logging.info(f"reset at {current_time}.")

        await notify_market_open_or_close(list_schedule, message_sent, current_time)

        # 다음 체크까지 대기 시간 계산
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
