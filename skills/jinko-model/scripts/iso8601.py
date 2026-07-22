"""Iso8601 module."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

# Conversion constants
SEC_PER_YEAR = 31557600  # 365.25 days
SEC_PER_MONTH = 2629800  # a year / 12
SEC_PER_WEEK = 604800  # 7 * 24 * 60 * 60
SEC_PER_DAY = 86400  # 60 * 60 * 24
SEC_PER_HOUR = 3600
SEC_PER_MINUTE = 60


@dataclass(frozen=True)
class Duration:
    """Representation of an ISO8601 duration using rational numbers."""

    years: Fraction = Fraction(0)
    months: Fraction = Fraction(0)
    weeks: Fraction = Fraction(0)
    days: Fraction = Fraction(0)
    hours: Fraction = Fraction(0)
    minutes: Fraction = Fraction(0)
    seconds: Fraction = Fraction(0)

    def __add__(self, other: Duration) -> Duration:
        """Add two durations."""
        return Duration(
            years=self.years + other.years,
            months=self.months + other.months,
            weeks=self.weeks + other.weeks,
            days=self.days + other.days,
            hours=self.hours + other.hours,
            minutes=self.minutes + other.minutes,
            seconds=self.seconds + other.seconds,
        )

    def __eq__(self, other: Any) -> bool:
        """Check equality."""
        if not isinstance(other, Duration):
            return False
        return (
            self.years == other.years
            and self.months == other.months
            and self.weeks == other.weeks
            and self.days == other.days
            and self.hours == other.hours
            and self.minutes == other.minutes
            and self.seconds == other.seconds
        )

    def is_zero(self) -> bool:
        """Check if the duration is exactly zero."""
        return self == Duration()


def duration_from_secs(seconds_double: float) -> Duration | None:
    """
    Convert a number of seconds to an ISO8601 duration.

    Parameters
    ----------
    seconds_double : float
        The number of seconds to convert.

    Returns
    -------
    Duration | None
        The duration object, or None if seconds_double is negative.
    """
    if seconds_double < 0:
        return None

    seconds = Fraction(seconds_double).limit_denominator(1000000000)

    # Special cases for exact multiples to avoid drift
    if (seconds / SEC_PER_WEEK).denominator == 1:
        return Duration(weeks=seconds / SEC_PER_WEEK)
    if (seconds / SEC_PER_DAY).denominator == 1:
        return Duration(days=seconds / SEC_PER_DAY)

    years_val = seconds / SEC_PER_YEAR
    num_years = int(years_val)
    rest_year = years_val - num_years

    # More special cases avoiding drift after years extraction
    if (rest_year * SEC_PER_YEAR / SEC_PER_WEEK).denominator == 1:
        return Duration(
            years=Fraction(num_years), weeks=(rest_year * SEC_PER_YEAR / SEC_PER_WEEK)
        )
    if (rest_year * SEC_PER_YEAR / SEC_PER_DAY).denominator == 1:
        return Duration(
            years=Fraction(num_years), days=(rest_year * SEC_PER_YEAR / SEC_PER_DAY)
        )

    months_val = rest_year * SEC_PER_YEAR / SEC_PER_MONTH
    num_months = int(months_val)
    rest_month = months_val - num_months

    weeks_val = rest_month * SEC_PER_MONTH / SEC_PER_WEEK
    num_weeks = int(weeks_val)
    rest_week = weeks_val - num_weeks

    days_val = rest_week * SEC_PER_WEEK / SEC_PER_DAY
    num_days = int(days_val)
    rest_day = days_val - num_days

    hours_val = rest_day * SEC_PER_DAY / SEC_PER_HOUR
    num_hours = int(hours_val)
    rest_hour = hours_val - num_hours

    minutes_val = rest_hour * SEC_PER_HOUR / SEC_PER_MINUTE
    num_minutes = int(minutes_val)
    rest_minute = minutes_val - num_minutes

    num_micro_seconds = round(float(rest_minute * SEC_PER_MINUTE * 1e6))

    return Duration(
        years=Fraction(num_years),
        months=Fraction(num_months),
        weeks=Fraction(num_weeks),
        days=Fraction(num_days),
        hours=Fraction(num_hours),
        minutes=Fraction(num_minutes),
        seconds=Fraction(num_micro_seconds, 1000000),
    )


def unsafe_duration_from_secs(seconds: float) -> Duration:
    """
    Convert seconds to duration, raising ValueError if negative.

    Parameters
    ----------
    seconds : float
        The number of seconds to convert.

    Returns
    -------
    Duration
        The duration object.

    Raises
    ------
    ValueError
        If the input seconds are negative.
    """
    dur = duration_from_secs(seconds)
    if dur is None:
        raise ValueError(
            f"cannot convert a negative number to an ISO8601 duration: {seconds}"
        )
    return dur


def duration_to_secs_rational(dur: Duration) -> Fraction:
    """
    Convert a Duration to a total number of seconds as a Fraction.

    Parameters
    ----------
    dur : Duration
        The duration to convert.

    Returns
    -------
    Fraction
        The total number of seconds.
    """
    return (
        dur.years * SEC_PER_YEAR
        + dur.months * SEC_PER_MONTH
        + dur.weeks * SEC_PER_WEEK
        + dur.days * SEC_PER_DAY
        + dur.hours * SEC_PER_HOUR
        + dur.minutes * SEC_PER_MINUTE
        + dur.seconds
    )


def duration_to_secs(dur: Duration) -> float:
    """
    Convert a Duration to a total number of seconds as a float.

    Parameters
    ----------
    dur : Duration
        The duration to convert.

    Returns
    -------
    float
        The total number of seconds.
    """
    return float(duration_to_secs_rational(dur))


def parse_duration(s: str) -> Duration | None:
    """
    Parse an ISO8601 duration string into a Duration object.

    Parameters
    ----------
    s : str
        The ISO8601 duration string (e.g., "P1DT2H").

    Returns
    -------
    Duration | None
        The parsed Duration object, or None if parsing fails.
    """
    if s in ("P", "PT"):
        return None

    # Do not uppercase blindly because Haskell tests expect "p" or lowercase units to fail
    # We want strictly ISO 8601 casing (P...Y...M...W...D...T...H...M...S...)
    pattern = (
        r"^P"
        r"(?:(?P<years>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)Y)?"
        r"(?:(?P<months>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)M)?"
        r"(?:(?P<weeks>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)W)?"
        r"(?:(?P<days>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)D)?"
        r"(?:T"
        r"(?:(?P<hours>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)H)?"
        r"(?:(?P<minutes>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)M)?"
        r"(?:(?P<seconds>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)S)?"
        r")?$"
    )

    match = re.match(pattern, s)

    if not match:
        return None

    # Check if there is at least one captured group
    if not any(v is not None for v in match.groups()):
        return None

    def _parse_fraction(val: str | None) -> Fraction:
        if val is None:
            return Fraction(0)
        return Fraction(float(val)).limit_denominator(1000000000)

    try:
        return Duration(
            years=_parse_fraction(match.group("years")),
            months=_parse_fraction(match.group("months")),
            weeks=_parse_fraction(match.group("weeks")),
            days=_parse_fraction(match.group("days")),
            hours=_parse_fraction(match.group("hours")),
            minutes=_parse_fraction(match.group("minutes")),
            seconds=_parse_fraction(match.group("seconds")),
        )
    except ValueError:
        return None


def unsafe_parse_duration(s: str) -> Duration:
    """
    Parse an ISO8601 duration string, raising ValueError if parsing fails.

    Parameters
    ----------
    s : str
        The ISO8601 duration string.

    Returns
    -------
    Duration
        The parsed Duration object.

    Raises
    ------
    ValueError
        If the string is not a valid ISO8601 duration.
    """
    dur = parse_duration(s)
    if dur is None:
        raise ValueError(f"Cannot parse {s} as Duration")
    return dur


def show_duration(dur: Duration) -> str:
    """
    Format a Duration object as an ISO8601 duration string.

    Parameters
    ----------
    dur : Duration
        The duration to format.

    Returns
    -------
    str
        The ISO8601 duration string.
    """
    if dur.is_zero():
        return "PT0S"

    def _format(suffix: str, count: Fraction) -> str:
        if count == 0:
            return ""
        if count.denominator == 1:
            return f"{count.numerator}{suffix}"
        # formatting to avoid scientific notation
        val = float(count)
        s_val = f"{val:f}".rstrip("0").rstrip(".")
        return f"{s_val}{suffix}"

    res = "P"
    res += _format("Y", dur.years)
    res += _format("M", dur.months)
    res += _format("W", dur.weeks)
    res += _format("D", dur.days)

    if dur.hours != 0 or dur.minutes != 0 or dur.seconds != 0:
        res += "T"
        res += _format("H", dur.hours)
        res += _format("M", dur.minutes)
        res += _format("S", dur.seconds)

    return res


def canonical_duration(dur: Duration) -> Duration:
    """
    Canonicalize a duration by converting it to seconds and back.

    Parameters
    ----------
    dur : Duration
        The duration to canonicalize.

    Returns
    -------
    Duration
        The canonicalized Duration.
    """
    return unsafe_duration_from_secs(duration_to_secs(dur))


def pretty_iso8601_duration(dur: Duration) -> str:
    """
    Format a duration into a human-readable string.

    Parameters
    ----------
    dur : Duration
        The duration to format.

    Returns
    -------
    str
        The human-readable string (e.g., "1 day 2 hours").
    """
    if dur.is_zero():
        return "0 seconds"

    def _format(val: Fraction, name: str) -> str | None:
        if val == 0:
            return None
        s_val = (
            f"{val.numerator}"
            if val.denominator == 1
            else f"{float(val):f}".rstrip("0").rstrip(".")
        )
        plural = "s" if float(val) != 1.0 else ""
        return f"{s_val} {name}{plural}"

    parts = [
        _format(dur.years, "year"),
        _format(dur.months, "month"),
        _format(dur.weeks, "week"),
        _format(dur.days, "day"),
        _format(dur.hours, "hour"),
        _format(dur.minutes, "minute"),
        _format(dur.seconds, "second"),
    ]
    return " ".join(p for p in parts if p is not None)


def _round_down_rational(n: Fraction) -> Fraction:
    if n >= 1:
        return Fraction(int(n))

    val = float(n)
    if val == 0.0:
        return Fraction(0)

    # find first non-null decimal
    s_val = f"{val:.15f}"
    parts = s_val.split(".")
    if len(parts) == 1:
        return n

    decimals = parts[1]
    for i, char in enumerate(decimals):
        if char != "0":
            # round to this decimal
            factor = 10 ** (i + 1)
            return Fraction(int(val * factor), factor)

    return n


def round_duration_down_to_full_unit(dur: Duration) -> Duration:
    """
    Round a duration down to its largest non-zero unit.

    Parameters
    ----------
    dur : Duration
        The duration to round.

    Returns
    -------
    Duration
        The rounded duration.
    """
    can_dur = canonical_duration(dur)

    if can_dur.years != 0:
        return Duration(years=can_dur.years)
    if can_dur.months != 0:
        return Duration(months=can_dur.months)
    if can_dur.weeks != 0:
        return Duration(weeks=can_dur.weeks)
    if can_dur.days != 0:
        return Duration(days=can_dur.days)
    if can_dur.hours != 0:
        return Duration(hours=can_dur.hours)
    if can_dur.minutes != 0:
        return Duration(minutes=can_dur.minutes)
    if can_dur.seconds != 0:
        return Duration(seconds=_round_down_rational(can_dur.seconds))

    return Duration()


def _round_up_rational(n: Fraction) -> Fraction:
    if n >= 1:
        if n.denominator == 1:
            return n
        return Fraction(int(n) + 1)

    val = float(n)
    if val == 0.0:
        return Fraction(0)

    s_val = f"{val:.15f}"
    parts = s_val.split(".")
    if len(parts) == 1:
        return n

    decimals = parts[1]
    for i, char in enumerate(decimals):
        if char != "0":
            factor = 10 ** (i + 1)
            # if there are further non-zero digits, ceil it properly
            if val * factor == int(val * factor):
                return Fraction(int(val * factor), factor)
            return Fraction(int(val * factor) + 1, factor)

    return n


def round_duration_up_to_full_unit(dur: Duration) -> Duration:
    """
    Round a duration up to its largest non-zero unit.

    Parameters
    ----------
    dur : Duration
        The duration to round.

    Returns
    -------
    Duration
        The rounded duration.
    """
    can_dur = canonical_duration(dur)

    if can_dur.years != 0:
        return (
            dur
            if can_dur == Duration(years=can_dur.years)
            else Duration(years=can_dur.years + Fraction(1))
        )
    if can_dur.months != 0:
        return (
            dur
            if can_dur == Duration(months=can_dur.months)
            else Duration(months=can_dur.months + Fraction(1))
        )
    if can_dur.weeks != 0:
        return (
            dur
            if can_dur == Duration(weeks=can_dur.weeks)
            else Duration(weeks=can_dur.weeks + Fraction(1))
        )
    if can_dur.days != 0:
        return (
            dur
            if can_dur == Duration(days=can_dur.days)
            else Duration(days=can_dur.days + Fraction(1))
        )
    if can_dur.hours != 0:
        return (
            dur
            if can_dur == Duration(hours=can_dur.hours)
            else Duration(hours=can_dur.hours + Fraction(1))
        )
    if can_dur.minutes != 0:
        return (
            dur
            if can_dur == Duration(minutes=can_dur.minutes)
            else Duration(minutes=can_dur.minutes + Fraction(1))
        )
    if can_dur.seconds != 0:
        return Duration(seconds=_round_up_rational(can_dur.seconds))

    return Duration()
