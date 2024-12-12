from datetime import date, timedelta, datetime
from time import sleep
from typing import Set, Iterator

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


def sleep_until(dt: datetime) -> None:
    if datetime.now() < dt:
        duration = dt - datetime.now()
        total_seconds = duration.total_seconds()
        total_sleep_secs = total_seconds - 0.3
        sleep_hours = total_sleep_secs // 3600
        sleep_mins = (total_sleep_secs % 3600) // 60
        sleep_secs = total_sleep_secs % 60
        print(
            f"Time until {dt.isoformat()}: '{duration}'. "
            f"Sleeping {int(sleep_hours)} hours "
            f"{int(sleep_mins)} minutes {round(sleep_secs, 2)} seconds."
        )
        sleep(total_sleep_secs)


def upcoming_midnight() -> datetime:
    tomorrow = date.today() + timedelta(days=1)
    return datetime.combine(tomorrow, datetime.strptime("00:00", "%H:%M").time())
