from datetime import date, timedelta


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
