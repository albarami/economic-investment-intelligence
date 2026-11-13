"""The fixed C25 rule and the two geometry-free rules of MTH-90."""

from fractions import Fraction

from .params import Parameters


def whole_speed(value: Fraction) -> int:
    """Round a nonnegative exact speed half-up to whole kilometres per hour."""
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def rounded_ratio(value: Fraction) -> str:
    scaled = value * 1000
    whole = (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)
    return f"{whole // 1000}.{whole % 1000:03d}"


def delay_factor(
    volume: Fraction, capacity: Fraction, parameters: Parameters
) -> Fraction:
    return 1 + parameters.alpha * (volume / capacity) ** parameters.beta


def volume_band(ratio: Fraction, parameters: Parameters) -> str:
    return f"vb{1 + sum(ratio >= edge for edge in parameters.edges)}"


def situation_mean(minutes: tuple[Fraction, ...]) -> Fraction:
    if not minutes:
        raise ValueError("NO_DATA: empty situation")
    return sum(minutes, Fraction(0)) / len(minutes)


def situation_whole_speed(length_m: Fraction, minutes: tuple[Fraction, ...]) -> int:
    """Whole km/h from the exact mean hourly minutes (decision 0021 item 8)."""
    return whole_speed(length_m * 60 / (1000 * situation_mean(minutes)))


def length_weighted_slowdown(
    links: tuple[tuple[Fraction, Fraction | None], ...],
) -> str:
    length = sum((item[0] for item in links), Fraction(0))
    if length <= 0:
        raise ValueError("NO_DATA: no road length")
    return rounded_ratio(
        sum(
            (
                distance * (Fraction(1) if ratio is None else ratio)
                for distance, ratio in links
            ),
            Fraction(0),
        )
        / length
    )
