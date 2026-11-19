"""Document 07 C30 wording; Part B binds placeholders to Fact chips."""

PUBLIC_SENTENCE = (
    "Forecast of {series} for {period}: {value}, range {low} to {high}. "
    "In the backtest {x} of {y} past values fell inside the range that the other "
    "past errors gave; its error was {error}."
)
SYNTHETIC_SENTENCE = (
    "Forecast of this area's released {series} for {month}: {value}, "
    "range {low} to {high}. In the backtest {x} of {y} past values fell inside "
    "the range that the other past errors gave; its error was {error}. "
    "These released periods show the format, not Qatar."
)
METHOD_LINE = "Method: {candidate}, chosen in code by backtest; source: {source}."
NOT_ENOUGH_HISTORY = "not enough history"
CAPTION_BINDINGS = (("x", "inside"), ("y", "tested"))

# These are declarations only. Canonical metadata/history chip bindings await
# the shared Fact family and the release fact emitter; no raw label fallback.
FACT_BINDINGS = (
    ("value", "forecast_value"),
    ("low", "forecast_low"),
    ("high", "forecast_high"),
    ("error", "forecast_backtest_error"),
    ("points", "forecast_backtest_points"),
    ("inside", "forecast_inside"),
    ("tested", "forecast_tested"),
)
CLAMP_BINDINGS = ("low_clamped", "high_clamped")
