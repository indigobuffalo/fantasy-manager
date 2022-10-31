from datetime import date, timedelta

DAYS_OF_WEEK = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6
}

def date_range(date1, date2):
    for n in range(int((date2 - date1).days) + 1):
        yield date1 + timedelta(n)


def current_season_years():
    today = date.today()
    month, year = today.month, today.year
    second_half_months = [1, 2, 3, 4, 5]

    if month in second_half_months:
        return {year - 1, year}
    else:
        return {year, year + 1}


def num_days_until(until_day: str, from_date: date = date.today()) -> int:
    days_until = 0
    end_date = from_date
    while end_date.weekday() != DAYS_OF_WEEK[until_day]:
        end_date += timedelta(days=1)
        days_until += 1
    return days_until
