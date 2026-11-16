"""Closed Comtrade policy, request descriptors and key-free failure text."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from eii_custodian.publicdata.fetch.allowlist import approve_closed, canonical_https
from eii_custodian.publicdata.fetch.receipts import sha256_hex

SOURCE_ID = "un_comtrade"
HEADER_NAME = "Ocp-Apim-Subscription-Key"
QATAR_REPORTER = "QAT"
PARSER_METHOD = "comtrade.parse"
PARSER_VERSION = "1"
SCHEMA_VERSION = 1
PERIOD_YEAR_LENGTH = 4
PERIOD_MONTH_LENGTH = 7
DAY_LENGTH = 10
FORBIDDEN_FAMILIES = frozenset({"deliver", "bulk", "async"})
API_CLASSES = frozenset({"keyed", "public"})
ROLES = frozenset({"reporter", "mirror"})
FREQUENCIES = frozenset({"annual", "monthly"})
_DATE_TEXT = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
_YEAR_TEXT = re.compile(r"\A\d{4}\Z")
_MONTH_TEXT = re.compile(r"\A\d{4}-\d{2}\Z")
_SHA = re.compile(r"\A[0-9a-f]{64}\Z")

POLICY_FIELDS = frozenset(
    {
        "confirmed",
        "version",
        "verified_on",
        "evidence_url",
        "evidence_sha256",
        "access_tier",
        "endpoint_templates",
        "allowed_redirect_hosts",
        "daily_calls",
        "keyed_record_limit",
        "public_record_limit",
        "reset_rule",
        "quota_scope",
        "daily_exhaustion_signal",
        "reporter_key",
        "mirror_partner_keys",
        "frequencies",
        "periods",
        "flows",
        "chapters",
        "subdivision_fields",
        "subdivision_values",
        "response_schema",
        "count_bounds",
        "classification_revision",
        "measure_units",
        "value_precision",
        "value_scale",
        "price_amount",
        "price_currency",
        "price_retrieved_on",
        "price_source",
        "price_unavailable_reason",
    }
)
TEMPLATE_FIELDS = frozenset({"api_class", "family", "host", "path"})
SCHEMA_FIELDS = frozenset(
    {
        "record_array",
        "count_field",
        "truncation_field",
        "error_field",
        "reporter_field",
        "partner_field",
        "partner2_field",
        "period_field",
        "flow_field",
        "product_field",
        "value_field",
        "quantity_field",
        "flag_field",
    }
)


class PolicyError(Exception):
    """The policy document is not acceptable."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class SafeRefusal(Exception):
    """A failure whose text is the source, a canonical URL, the check and an endpoint id."""

    check: str
    safe_url: str
    endpoint_id: str
    source_id: str = SOURCE_ID

    def __str__(self) -> str:
        return (
            f"{self.source_id} {self.safe_url} {self.check} endpoint={self.endpoint_id}"
        )


@dataclass(frozen=True)
class EndpointTemplate:
    """One allow-listed host and path for an API class. No query is stored."""

    api_class: str
    family: str
    host: str
    path: str


@dataclass(frozen=True)
class ResponseSchema:
    """Invented or lead-reviewed field names. Values are strings, never computed."""

    record_array: str
    count_field: str
    truncation_field: str
    error_field: str
    reporter_field: str
    partner_field: str
    partner2_field: str
    period_field: str
    flow_field: str
    product_field: str
    value_field: str
    quantity_field: str
    flag_field: str


@dataclass(frozen=True)
class CountBounds:
    """Inclusive row-count bounds. The policy is canonical."""

    minimum: int
    maximum: int


@dataclass(frozen=True)
class UnconfirmedPolicy:
    """A registry policy that the lead has not activated."""

    confirmed: bool = False


@dataclass(frozen=True)
class Policy:
    """One activated closed policy. Limits and the selection are registry facts."""

    version: str
    verified_on: str
    evidence_url: str
    evidence_sha256: str
    access_tier: str
    endpoint_templates: tuple[EndpointTemplate, ...]
    allowed_redirect_hosts: tuple[str, ...]
    daily_calls: int
    keyed_record_limit: int
    public_record_limit: int
    reset_rule: str
    quota_scope: str
    daily_exhaustion_signal: str
    reporter_key: str
    mirror_partner_keys: tuple[str, ...]
    frequencies: tuple[str, ...]
    periods: tuple[str, ...]
    flows: tuple[str, ...]
    chapters: tuple[str, ...]
    subdivision_fields: tuple[str, ...]
    subdivision_values: tuple[tuple[str, tuple[str, ...]], ...]
    response_schema: ResponseSchema
    count_bounds: CountBounds
    classification_revision: str
    measure_units: tuple[tuple[str, str], ...]
    value_precision: int
    value_scale: int
    price_amount: str
    price_currency: str
    price_retrieved_on: str
    price_source: str
    price_unavailable_reason: str
    confirmed: bool = True

    def limit_for(self, api_class: str) -> int:
        """Return the per-call record cap of one API class."""
        if api_class == "public":
            return self.public_record_limit
        return self.keyed_record_limit

    def template(self, api_class: str, family: str) -> EndpointTemplate | None:
        """Return the template for one class and family, if it is listed."""
        for item in self.endpoint_templates:
            if item.api_class == api_class and item.family == family:
                return item
        return None


@dataclass(frozen=True)
class Descriptor:
    """A closed request. Transport builds the address from this and the policy."""

    api_class: str
    endpoint_family: str
    series_role: str
    reporter_code: str
    partner_code: str
    frequency: str
    period: str
    flow_code: str
    chapter: str
    classification_revision: str
    subdivision: tuple[tuple[str, str], ...] = ()

    def endpoint_id(self) -> str:
        """Return a stable identifier that is not an address."""
        parts = (
            self.api_class,
            self.endpoint_family,
            self.series_role,
            self.reporter_code,
            self.partner_code,
            self.frequency,
            self.period,
            self.flow_code,
            self.chapter,
            self.classification_revision,
        )
        extra = ",".join(f"{name}={value}" for name, value in self.subdivision)
        return "/".join(parts) + ("/" + extra if extra else "")

    def selectors(self) -> tuple[tuple[str, str], ...]:
        """Return the closed query selectors in a fixed order."""
        base = (
            ("chapter", self.chapter),
            ("flow", self.flow_code),
            ("frequency", self.frequency),
            ("partner", self.partner_code),
            ("period", self.period),
            ("reporter", self.reporter_code),
            ("revision", self.classification_revision),
            ("role", self.series_role),
        )
        return base + tuple(sorted(self.subdivision))


def parse_policy(raw: object) -> Policy | UnconfirmedPolicy:
    """Parse a registry policy. Unknown fields are refused. Incomplete stays unconfirmed."""
    if not isinstance(raw, dict):
        raise PolicyError("comtrade_policy is not a map")
    unknown = set(raw) - POLICY_FIELDS
    if unknown:
        raise PolicyError(
            "unknown comtrade_policy field "
            + ",".join(sorted(str(item) for item in unknown))
        )
    confirmed = raw.get("confirmed")
    if confirmed is False:
        if set(raw) - {"confirmed"}:
            raise PolicyError("unconfirmed policy has fields")
        return UnconfirmedPolicy()
    if confirmed is not True:
        raise PolicyError("confirmed is not a boolean")
    return _activated(raw)


def activation_check(
    policy: Policy | UnconfirmedPolicy | None,
    *,
    row_count_min: int | None,
    row_count_max: int | None,
    period_first: str,
    period_last: str,
    licence_basis: str,
    decision_record: str,
) -> str | None:
    """Return the failed check, or None when the row matches the canonical policy."""
    if not isinstance(policy, Policy) or not policy.confirmed:
        return "metadata_unconfirmed"
    if licence_basis != "provider_terms" or decision_record != "":
        return "licence_basis"
    if (
        row_count_min != policy.count_bounds.minimum
        or row_count_max != policy.count_bounds.maximum
    ):
        return "count_bounds"
    first, last = period_ends(policy.periods)
    if period_first != first or period_last != last:
        return "period_bounds"
    if not _frequencies_match(policy):
        return "period_frequency"
    return None


def period_ends(periods: tuple[str, ...]) -> tuple[str, str]:
    """Return the earliest and latest period. The policy list is the selection."""
    ordered = tuple(sorted(periods))
    return ordered[0], ordered[-1]


def direction_ok(policy: Policy, descriptor: Descriptor) -> bool:
    """Reporter requests use Qatar. Mirror requests use the partner, with Qatar as partner."""
    if descriptor.series_role == "reporter":
        return (
            descriptor.reporter_code == policy.reporter_key
            and descriptor.partner_code in policy.mirror_partner_keys
        )
    if descriptor.series_role == "mirror":
        return (
            descriptor.reporter_code in policy.mirror_partner_keys
            and descriptor.partner_code == policy.reporter_key
        )
    return False


def safe_url(policy: Policy, descriptor: Descriptor) -> str:
    """Return the canonical URL, or a host-only URL when the family is not a template."""
    template = policy.template(descriptor.api_class, descriptor.endpoint_family)
    if template is None:
        host = policy.endpoint_templates[0].host
        return canonical_https(host, "/refused", ())
    return canonical_https(template.host, template.path, descriptor.selectors())


def url_approved(policy: Policy, descriptor: Descriptor) -> bool:
    """Return whether the canonical URL is on the policy hosts with those selectors."""
    template = policy.template(descriptor.api_class, descriptor.endpoint_family)
    if template is None:
        return False
    if template.family in FORBIDDEN_FAMILIES:
        return False
    url = canonical_https(template.host, template.path, descriptor.selectors())
    hosts = frozenset(item.host for item in policy.endpoint_templates)
    decision = approve_closed(url, hosts=hosts, selectors=descriptor.selectors())
    return decision.ok


def refusal(policy: Policy, descriptor: Descriptor, check: str) -> SafeRefusal:
    """Build a refusal. The URL is canonical even when the check is a bad family."""
    try:
        url = safe_url(policy, descriptor)
    except ValueError:
        url = "https://invalid.example/refused"
    return SafeRefusal(check, url, descriptor.endpoint_id())


def policy_sha256(policy: Policy) -> str:
    """Hash the canonical policy. The selection is included, so a change is visible."""
    return sha256_hex(_dump(_policy_payload(policy)))


def selection_sha256(policy: Policy) -> str:
    """Hash only the closed selection. It is never taken from a fetched ranking."""
    payload = {
        "chapters": list(policy.chapters),
        "flows": list(policy.flows),
        "frequencies": list(policy.frequencies),
        "partners": list(policy.mirror_partner_keys),
        "periods": list(policy.periods),
        "revision": policy.classification_revision,
        "reporter": policy.reporter_key,
    }
    return sha256_hex(_dump(payload))


def contains_secret(text: str, secret: str) -> bool:
    """Return whether text holds a non-empty secret. The empty string is never a secret."""
    if secret == "":
        return False
    return secret in text


def _activated(raw: Mapping[object, object]) -> Policy:
    missing = POLICY_FIELDS - set(raw)
    if missing:
        raise PolicyError(
            "missing comtrade_policy field "
            + ",".join(sorted(str(item) for item in missing))
        )
    daily = _positive(raw, "daily_calls")
    keyed = _positive(raw, "keyed_record_limit")
    public = _positive(raw, "public_record_limit")
    precision = _positive(raw, "value_precision")
    scale = _non_negative(raw, "value_scale")
    if scale >= precision:
        raise PolicyError("value_scale is not below precision")
    bounds = _bounds(raw.get("count_bounds"))
    templates = _templates(raw.get("endpoint_templates"))
    schema = _schema(raw.get("response_schema"))
    frequencies = _choice_list(raw, "frequencies", FREQUENCIES)
    periods = _periods(raw.get("periods"), frequencies)
    partners = _text_list(raw, "mirror_partner_keys")
    reporter = _text_value(raw, "reporter_key")
    if reporter == "" or reporter in partners:
        raise PolicyError("reporter_key")
    measures = _pairs(raw.get("measure_units"))
    subdivisions = _subdivision(
        raw.get("subdivision_fields"), raw.get("subdivision_values")
    )
    verified = _text_value(raw, "verified_on")
    if _DATE_TEXT.fullmatch(verified) is None:
        raise PolicyError("verified_on is not a date")
    evidence_hash = _text_value(raw, "evidence_sha256")
    if _SHA.fullmatch(evidence_hash) is None:
        raise PolicyError("evidence_sha256")
    price_on = _text_value(raw, "price_retrieved_on")
    if price_on and _DATE_TEXT.fullmatch(price_on) is None:
        raise PolicyError("price_retrieved_on is not a date")
    amount = _text_value(raw, "price_amount")
    reason = _text_value(raw, "price_unavailable_reason")
    if amount == "" and reason == "":
        raise PolicyError("price evidence")
    if amount != "" and reason != "":
        raise PolicyError("price evidence")
    return Policy(
        version=_text_value(raw, "version"),
        verified_on=verified,
        evidence_url=_text_value(raw, "evidence_url"),
        evidence_sha256=evidence_hash,
        access_tier=_text_value(raw, "access_tier"),
        endpoint_templates=templates,
        allowed_redirect_hosts=_text_list(raw, "allowed_redirect_hosts"),
        daily_calls=daily,
        keyed_record_limit=keyed,
        public_record_limit=public,
        reset_rule=_text_value(raw, "reset_rule"),
        quota_scope=_text_value(raw, "quota_scope"),
        daily_exhaustion_signal=_text_value(raw, "daily_exhaustion_signal"),
        reporter_key=reporter,
        mirror_partner_keys=partners,
        frequencies=frequencies,
        periods=periods,
        flows=_text_list(raw, "flows"),
        chapters=_text_list(raw, "chapters"),
        subdivision_fields=subdivisions[0],
        subdivision_values=subdivisions[1],
        response_schema=schema,
        count_bounds=bounds,
        classification_revision=_text_value(raw, "classification_revision"),
        measure_units=measures,
        value_precision=precision,
        value_scale=scale,
        price_amount=amount,
        price_currency=_text_value(raw, "price_currency"),
        price_retrieved_on=price_on,
        price_source=_text_value(raw, "price_source"),
        price_unavailable_reason=reason,
    )


def _frequencies_match(policy: Policy) -> bool:
    annual = [item for item in policy.periods if _YEAR_TEXT.fullmatch(item)]
    monthly = [item for item in policy.periods if _MONTH_TEXT.fullmatch(item)]
    if "annual" in policy.frequencies and not annual:
        return False
    if "monthly" in policy.frequencies and not monthly:
        return False
    if "annual" not in policy.frequencies and annual:
        return False
    if "monthly" not in policy.frequencies and monthly:
        return False
    return True


def _periods(value: object, frequencies: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise PolicyError("periods")
    found: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PolicyError("periods")
        if _YEAR_TEXT.fullmatch(item) or _MONTH_TEXT.fullmatch(item):
            found.append(item)
            continue
        raise PolicyError("periods")
    if len(found) != len(set(found)):
        raise PolicyError("periods")
    del frequencies
    return tuple(sorted(found))


def _bounds(value: object) -> CountBounds:
    if not isinstance(value, dict):
        raise PolicyError("count_bounds")
    if set(value) != {"minimum", "maximum"}:
        raise PolicyError("count_bounds")
    minimum = value.get("minimum")
    maximum = value.get("maximum")
    if isinstance(minimum, bool) or not isinstance(minimum, int):
        raise PolicyError("count_bounds")
    if isinstance(maximum, bool) or not isinstance(maximum, int):
        raise PolicyError("count_bounds")
    if minimum < 0 or maximum < minimum:
        raise PolicyError("count_bounds")
    return CountBounds(minimum, maximum)


def _templates(value: object) -> tuple[EndpointTemplate, ...]:
    if not isinstance(value, list) or not value:
        raise PolicyError("endpoint_templates")
    found: list[EndpointTemplate] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != TEMPLATE_FIELDS:
            raise PolicyError("endpoint_templates")
        api_class = item.get("api_class")
        family = item.get("family")
        host = item.get("host")
        path = item.get("path")
        if not isinstance(api_class, str) or api_class not in API_CLASSES:
            raise PolicyError("endpoint_templates")
        if not isinstance(family, str) or family == "" or family in FORBIDDEN_FAMILIES:
            raise PolicyError("endpoint_templates")
        if not isinstance(host, str) or not isinstance(path, str):
            raise PolicyError("endpoint_templates")
        lowered = family.casefold()
        if any(
            token in lowered or token in path.casefold() for token in FORBIDDEN_FAMILIES
        ):
            raise PolicyError("endpoint_templates")
        try:
            canonical_https(host, path, ())
        except ValueError as exc:
            raise PolicyError("endpoint_templates") from exc
        found.append(EndpointTemplate(api_class, family, host.casefold(), path))
    return tuple(found)


def _schema(value: object) -> ResponseSchema:
    if not isinstance(value, dict) or set(value) != SCHEMA_FIELDS:
        raise PolicyError("response_schema")
    texts: dict[str, str] = {}
    for name in SCHEMA_FIELDS:
        item = value.get(name)
        if not isinstance(item, str) or item == "":
            raise PolicyError("response_schema")
        texts[name] = item
    return ResponseSchema(
        record_array=texts["record_array"],
        count_field=texts["count_field"],
        truncation_field=texts["truncation_field"],
        error_field=texts["error_field"],
        reporter_field=texts["reporter_field"],
        partner_field=texts["partner_field"],
        partner2_field=texts["partner2_field"],
        period_field=texts["period_field"],
        flow_field=texts["flow_field"],
        product_field=texts["product_field"],
        value_field=texts["value_field"],
        quantity_field=texts["quantity_field"],
        flag_field=texts["flag_field"],
    )


def _subdivision(
    fields: object, values: object
) -> tuple[tuple[str, ...], tuple[tuple[str, tuple[str, ...]], ...]]:
    names = _plain_list(fields, "subdivision_fields")
    if not isinstance(values, dict) or set(values) != set(names):
        raise PolicyError("subdivision_values")
    pairs: list[tuple[str, tuple[str, ...]]] = []
    for name in names:
        options = values.get(name)
        if not isinstance(options, list) or not options:
            raise PolicyError("subdivision_values")
        if not all(isinstance(item, str) and item != "" for item in options):
            raise PolicyError("subdivision_values")
        if len(options) != len(set(options)):
            raise PolicyError("subdivision_values")
        pairs.append((name, tuple(str(item) for item in options)))
    return names, tuple(pairs)


def _pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list) or not value:
        raise PolicyError("measure_units")
    found: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"measure", "unit"}:
            raise PolicyError("measure_units")
        measure = item.get("measure")
        unit = item.get("unit")
        if not isinstance(measure, str) or not isinstance(unit, str):
            raise PolicyError("measure_units")
        if measure == "" or unit == "":
            raise PolicyError("measure_units")
        found.append((measure, unit))
    return tuple(found)


def _choice_list(
    raw: Mapping[object, object], name: str, allowed: frozenset[str]
) -> tuple[str, ...]:
    found = _text_list(raw, name)
    if not found or any(item not in allowed for item in found):
        raise PolicyError(name)
    return found


def _text_list(raw: Mapping[object, object], name: str) -> tuple[str, ...]:
    return _plain_list(raw.get(name), name)


def _plain_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PolicyError(name)
    if not all(isinstance(item, str) for item in value):
        raise PolicyError(name)
    texts = tuple(item for item in value if isinstance(item, str))
    if any(item == "" for item in texts) or len(texts) != len(set(texts)):
        raise PolicyError(name)
    return texts


def _text_value(raw: Mapping[object, object], name: str) -> str:
    value = raw.get(name)
    if not isinstance(value, str):
        raise PolicyError(name)
    return value


def _positive(raw: Mapping[object, object], name: str) -> int:
    value = _non_negative(raw, name)
    if value < 1:
        raise PolicyError(name)
    return value


def _non_negative(raw: Mapping[object, object], name: str) -> int:
    value = raw.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PolicyError(name)
    return value


def _policy_payload(policy: Policy) -> dict[str, object]:
    return {
        "access_tier": policy.access_tier,
        "chapters": list(policy.chapters),
        "classification_revision": policy.classification_revision,
        "count_bounds": {
            "maximum": policy.count_bounds.maximum,
            "minimum": policy.count_bounds.minimum,
        },
        "daily_calls": policy.daily_calls,
        "daily_exhaustion_signal": policy.daily_exhaustion_signal,
        "endpoint_templates": [
            {
                "api_class": item.api_class,
                "family": item.family,
                "host": item.host,
                "path": item.path,
            }
            for item in policy.endpoint_templates
        ],
        "flows": list(policy.flows),
        "frequencies": list(policy.frequencies),
        "keyed_record_limit": policy.keyed_record_limit,
        "measure_units": [
            {"measure": measure, "unit": unit} for measure, unit in policy.measure_units
        ],
        "mirror_partner_keys": list(policy.mirror_partner_keys),
        "periods": list(policy.periods),
        "public_record_limit": policy.public_record_limit,
        "quota_scope": policy.quota_scope,
        "reporter_key": policy.reporter_key,
        "reset_rule": policy.reset_rule,
        "subdivision_fields": list(policy.subdivision_fields),
        "value_precision": policy.value_precision,
        "value_scale": policy.value_scale,
        "version": policy.version,
    }


def _dump(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
