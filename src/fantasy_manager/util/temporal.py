from datetime import date, timedelta, datetime
import logging
from time import sleep
from typing import Iterator

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


def seconds_to_hours_mins_and_secs(seconds: float) -> tuple[float, float, float]:
    """Convert a duration represented as total seconds into hours, minutes and seconds"""
    seconds = abs(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return hours, minutes, seconds


def sleep_until(dt: datetime, logger: logging.Logger) -> None:
    if datetime.now() < dt:
        duration = dt - datetime.now()
        total_seconds = duration.total_seconds()
        total_sleep_secs = total_seconds - 0.2
        sleep_hours, sleep_mins, sleep_secs = seconds_to_hours_mins_and_secs(
            total_sleep_secs
        )
        logger.info(
            f"Time until {dt.isoformat()}: '{duration}'. "
            f"Sleeping {int(sleep_hours)} hours "
            f"{int(sleep_mins)} minutes {round(sleep_secs, 2)} seconds."
        )
        sleep(total_sleep_secs)


def sleep_verbose(sleep_seconds: float, logger: logging.Logger) -> None:
    logger.info(f"Sleeping for {sleep_seconds} seconds...")
    sleep(sleep_seconds)


def upcoming_midnight() -> datetime:
    tomorrow = date.today() + timedelta(days=1)
    return datetime.combine(tomorrow, datetime.strptime("00:00", "%H:%M").time())


def get_time_until_start_str(start: datetime) -> str:
    """Get loggable string that depicts time remaining before exectution.
    Args:
        start (datetime): The time of execution.
    Returns:
        str: A loggable str that informs the user of time until exection.
    """
    hours, mins, secs = seconds_to_hours_mins_and_secs(
        (datetime.now() - start).total_seconds()
    )
    return f"{int(hours)} HOURS {int(mins)} MINUTES {int(secs)} SECONDS"
