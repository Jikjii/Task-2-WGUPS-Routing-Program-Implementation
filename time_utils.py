"""
time_utils.py - Small helpers for working with clock times.

All times in the program are stored as datetime.timedelta values measured from
midnight. For example, 8:00 AM is timedelta(hours=8) and 1:30 PM is
timedelta(hours=13, minutes=30). A timedelta can be added, subtracted, and compared
directly, which keeps the delivery math simple and exact.
"""

import datetime
import math


def clock_time(hours, minutes=0):
    """Build a time of day (as a timedelta since midnight)."""
    return datetime.timedelta(hours=hours, minutes=minutes)


def travel_time(miles, speed_mph):
    """How long it takes to drive `miles` at a constant `speed_mph`."""
    return datetime.timedelta(hours=miles / speed_mph)


def parse_time(text):
    """
    Turn user or file text such as "9:05 am", "10:30 AM", "13:15" or "1:05pm" into a
    timedelta. Raise ValueError with a friendly message if the text is not a valid time.
    """
    cleaned = text.strip().lower().replace(".", "").replace(" ", "")
    suffix = ""
    if cleaned.endswith("am") or cleaned.endswith("pm"):
        suffix = cleaned[-2:]
        cleaned = cleaned[:-2]

    parts = cleaned.split(":")
    if len(parts) == 1 and parts[0].isdigit():
        parts.append("0")  # allow "9 am" as shorthand for "9:00 am"
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError(f"'{text}' is not a valid time. Use a format like 9:30 AM or 13:15.")

    hours, minutes = int(parts[0]), int(parts[1])
    if minutes > 59:
        raise ValueError(f"'{text}' is not a valid time: minutes must be 00-59.")

    if suffix:
        # 12-hour clock: 12 AM is midnight (0), 12 PM is noon (12).
        if hours < 1 or hours > 12:
            raise ValueError(f"'{text}' is not a valid time: hours must be 1-12 with AM/PM.")
        if suffix == "am":
            hours = 0 if hours == 12 else hours
        else:
            hours = 12 if hours == 12 else hours + 12
    elif hours > 23:
        raise ValueError(f"'{text}' is not a valid time: hours must be 0-23.")

    return clock_time(hours, minutes)


def format_time(time_value):
    """
    Show a timedelta-since-midnight as a 12-hour clock string, e.g. '09:05 AM'.

    Seconds are rounded UP to the next whole minute. Then a package shown as
    "Delivered at 09:24 AM" also reads as delivered when the user asks for its status
    at exactly 9:24 AM. The program's own deadline checks always use the exact time.
    """
    total_seconds = math.ceil(round(time_value.total_seconds(), 6) / 60) * 60
    hours = (total_seconds // 3600) % 24
    minutes = (total_seconds % 3600) // 60
    suffix = "AM" if hours < 12 else "PM"
    display_hour = hours % 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour:02d}:{minutes:02d} {suffix}"
