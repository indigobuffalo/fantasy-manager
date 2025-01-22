from datetime import date, time, timedelta, datetime, timezone
import logging
from time import sleep
from typing import Iterator
from zoneinfo import ZoneInfo

DAYS_OF_WEEK = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


def date_range(date1, date2) -> Iterator[date]:
    for n in range(int((date2 - date1).days) + 1):
        yield date1 + timedelta(n)


def days_until(until_day: str, from_date: date = date.today()) -> int:
    days_until = 0
    end_date = from_date
    while end_date.weekday() != DAYS_OF_WEEK[until_day]:
        end_date += timedelta(days=1)
        days_until += 1
    return days_until


def duration_to_hours_mins_and_secs(duration: timedelta) -> tuple[float, float, float]:
    """Convert a duration represented into hours, minutes and seconds"""
    seconds = abs(duration.total_seconds())
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return hours, minutes, seconds


def sleep_until(dt: datetime, logger: logging.Logger) -> None:
    now = now_pacific()
    if now < dt:
        total_duration = dt - now
        sleep_duration = total_duration - timedelta(seconds=0.2)
        sleep_hours, sleep_mins, sleep_secs = duration_to_hours_mins_and_secs(
            sleep_duration
        )
        logger.info(
            f"Time until {dt.isoformat()}: '{total_duration}'. "
            f"Sleeping {int(sleep_hours)} hours "
            f"{int(sleep_mins)} minutes {round(sleep_secs, 2)} seconds."
        )
        sleep(sleep_duration.total_seconds())


def sleep_verbose(sleep_seconds: float, logger: logging.Logger) -> None:
    logger.info(f"Sleeping for {sleep_seconds} seconds...")
    sleep(sleep_seconds)


def upcoming_midnight_pacific() -> datetime:
    """
    Returns midnight Pacific time (00:00) on the current day,
    considering the difference between PST and PDT.
    """
    pacific_tz = ZoneInfo("America/Los_Angeles")
    now_utc = datetime.now(timezone.utc)
    tomorrow_pacific = now_utc.astimezone(pacific_tz).date() + timedelta(days=1)
    return datetime.combine(tomorrow_pacific, time(0), tzinfo=pacific_tz)


def now_pacific() -> datetime:
    """Gets current datetime for the "America/Los_Angeles" timezone,
    which is the timezone Yahoo uses to determine EOD.

    Returns:
        datetime: The present datetime in the Pacific timezone.
    """
    return datetime.now(ZoneInfo("America/Los_Angeles"))


def get_timeout_end(start: datetime, timeout_seconds: int) -> datetime:
    now = datetime.now(timezone.utc)
    if start >= now:
        return start + timedelta(seconds=timeout_seconds)
    return now + timedelta(seconds=timeout_seconds)
