"""Independent MTH-03 file-path replays, for invented pass-1 inputs only.

Assumed shapes for pass 2 confirmation:
* Wilson/customs/property: JSON row arrays with the registry's column names.
* C5: per basket line, the mapping of invented line name to its fine codes.
* C6: Overture-shaped Parquet through the existing file reader, with an
  explicitly supplied projection from longitude/latitude to metric coordinates
  and the research-box, false-discovery and keep thresholds as parameters.
  The fixture projection is invented; confirm the live projection and receipt.
* C7: normalized JSON districts (district_key,value) and whole-centroid area
  membership lists, NOT an assumed raw ArcGIS layer shape. Live geometry and
  membership replay is deferred until those source fields/settings are known.
* Property crosswalk: JSON name->district and reviewed Arabic-type array.

These test-only oracles read paths supplied by the caller. They do not read the
S2-T08 produced-pin artifact and do not implement new production calculations.
"""

import json
import random
from collections import defaultdict
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path
from statistics import median


def rows(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"), parse_float=D)
    if not isinstance(value, list):
        raise ValueError("invented_replay_rows")
    return value


def replay_wilson(active_path, cancelled_path, *, municipality, activity, period):
    period = tuple(period)

    def selected(row):
        return row["lbldy"] == municipality and row["rmz_lnsht_ltjry"] == activity

    active = [row for row in rows(active_path) if selected(row)]
    cancelled = [
        row
        for row in rows(cancelled_path)
        if selected(row) and f"{row['sn_llg']}-{int(row['shhr_llg']):02}" in period
    ]
    n = sum(row["dd_lrkhs_lnsht"] for row in active)
    k = sum(row["dd_lrkhs_lmlg"] for row in cancelled)
    if n <= 0 or k < 0 or k > n or not period:
        raise ValueError("wilson_counts_or_period")
    with localcontext() as context:
        context.prec = 50
        z, size, p = D("1.96"), D(n), D(k) / D(n)
        denominator = 1 + z * z / size
        centre = (p + z * z / (2 * size)) / denominator
        half = z * (p * (1 - p) / size + z * z / (4 * size * size)).sqrt() / denominator
        return {
            "period": period[0] + ".." + period[-1],
            "k": k,
            "n": n,
            "low": format(centre - half, ".6f"),
            "high": format(centre + half, ".6f"),
            "z": str(z),
        }


def replay_c5(prior_path, latest_path, *, prior_months, latest_months, basket_lines):
    """Per basket line h: origin shares, HHI and the twelve-month trend."""
    previous, current = rows(prior_path), rows(latest_path)
    result = {}
    for line, fine_codes in basket_lines.items():
        codes = {code.replace(".", "") for code in fine_codes}
        parents = {code[:8] for code in codes}
        selected_old = [
            row
            for row in previous
            if row["hs8"].replace(".", "") in parents
            and f"{row['lsn_year']}-{int(row['lshhr_month']):02}" in prior_months
        ]
        selected_new = [
            row
            for row in current
            if row["harmonized_system_code"].replace(".", "") in codes
            and f"{row['year']}-{int(row['month']):02}" in latest_months
        ]
        prior = sum((D(row["value_qr"]) for row in selected_old), D(0))
        origins = defaultdict(lambda: D(0))
        for row in selected_new:
            # Missing/zero weight never removes a row from value share or HHI.
            origins[row["country_of_origin"]] += D(row["value_in_qatari_riyals"])
        latest = sum(origins.values(), D(0))
        hhi = (
            sum((D(10000) * (value / latest) ** 2 for value in origins.values()), D(0))
            if latest
            else "NO_DATA"
        )
        result[line] = {
            "hhi": hhi,
            "prior12": prior,
            "latest12": latest,
            "trend": (latest - prior) / prior if prior else "NO_DATA",
        }
    return result


def replay_c6(
    places_path,
    *,
    focal,
    candidates,
    seed,
    radius_m,
    confidence_min,
    permutations,
    project,
    box,
    fdr,
    min_neighbours,
    min_clq,
    max_shown,
):
    """Radius CLQ with permutation p and BH q, filtered to the kept display list.

    Points outside the research ``box`` (lat_min, lat_max, lon_min, lon_max)
    are dropped before projection. A candidate is kept when its count is at
    least ``min_neighbours``, its CLQ at least ``min_clq`` and its q at most
    ``fdr``; the kept list is ordered by (-clq, candidate) and cut to
    ``max_shown``.
    """
    from eii_custodian.publicdata.places.read import read_place_file

    lat_min, lat_max, lon_min, lon_max = box
    points = []
    for row in read_place_file(Path(places_path), "ar"):
        if row.confidence is not None and row.confidence >= confidence_min:
            if not (lat_min <= row.lat <= lat_max and lon_min <= row.lon <= lon_max):
                continue
            x, y = project(row.lon, row.lat)
            points.append({"x_m": x, "y_m": y, "category": row.category})
    labels = [row["category"] for row in points]
    neighbours = []
    for i, point in enumerate(points):
        neighbours.append(
            [
                j
                for j, other in enumerate(points)
                if i != j
                and (D(point["x_m"]) - D(other["x_m"])) ** 2
                + (D(point["y_m"]) - D(other["y_m"])) ** 2
                <= radius_m**2
            ]
        )

    def quotient(shuffled, candidate):
        focal_rows = [
            i for i, label in enumerate(shuffled) if label in focal and neighbours[i]
        ]
        n_candidate = shuffled.count(candidate)
        # Fixture candidates are disjoint from the focal definition. A live
        # same-category candidate needs the card's N_B - 1 rule too.
        if candidate in focal:
            raise ValueError("invented_fixture_disjoint_candidates_required")
        if not focal_rows or n_candidate == 0 or len(shuffled) <= 1:
            raise ValueError("c6_no_denominator")
        local = sum(
            (
                D(sum(shuffled[j] == candidate for j in neighbours[i]))
                / len(neighbours[i])
                for i in focal_rows
            ),
            D(0),
        ) / len(focal_rows)
        return local / (D(n_candidate) / (len(shuffled) - 1))

    observed = {candidate: quotient(labels, candidate) for candidate in candidates}
    exceeds = dict.fromkeys(candidates, 0)
    generator = random.Random(seed)
    for _ in range(permutations):
        shuffled = list(labels)
        generator.shuffle(shuffled)
        for candidate in candidates:
            if quotient(shuffled, candidate) >= observed[candidate]:
                exceeds[candidate] += 1
    ps = {
        candidate: D(1 + exceeds[candidate]) / (1 + permutations)
        for candidate in candidates
    }
    order = sorted(candidates, key=lambda candidate: (ps[candidate], candidate))
    adjusted = {}
    ceiling = D(1)
    for rank in range(len(order), 0, -1):
        candidate = order[rank - 1]
        ceiling = min(ceiling, ps[candidate] * len(order) / rank)
        adjusted[candidate] = ceiling
    stats = {
        candidate: {
            "clq": observed[candidate],
            "p": ps[candidate],
            "q": adjusted[candidate],
            "n_focal": sum(
                label in focal and bool(neighbours[i]) for i, label in enumerate(labels)
            ),
            "n_neighbour": labels.count(candidate),
        }
        for candidate in candidates
    }
    kept = [
        {"candidate": candidate, **row}
        for candidate, row in stats.items()
        if row["n_neighbour"] >= min_neighbours
        and row["clq"] >= min_clq
        and row["q"] <= fdr
    ]
    kept.sort(key=lambda row: (-row["clq"], row["candidate"]))
    return kept[:max_shown]


def replay_c7(weights_path, areas_path):
    weights = {row["district_key"]: D(row["value"]) for row in rows(weights_path)}
    areas = json.loads(Path(areas_path).read_text(encoding="utf-8"))
    a, b = set(areas["a"]), set(areas["b"])
    if (a | b) - weights.keys():
        raise ValueError("c7_unknown_district")
    wa, wb, overlap = (
        sum((weights[key] for key in keys), D(0)) for keys in (a, b, a & b)
    )
    if wa == 0 or wb == 0:
        return "NO_DATA", "NO_DATA"
    return overlap / wb, overlap / wa


def replay_c14(deals_path, crosswalk_path):
    crosswalk = json.loads(Path(crosswalk_path).read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for row in rows(deals_path):
        district = crosswalk["names"].get(row["district_name"])
        if district is None:
            continue
        kind = row["nw_l_qr"]
        if kind not in crosswalk["arabic_types"]:
            raise ValueError("unreviewed_arabic_type")
        price, area = D(row["property_value"]), D(row["area_square_meters"])
        if price <= 0 or area <= 0:
            continue
        year = row["registration_date"][:4]
        groups[district, year, kind].append(price / area)
    if not groups:
        return "NO_DATA"
    return {key: (median(values), len(values)) for key, values in groups.items()}


def assert_record_matches_replay(entries, replayed):
    """Fail when a checked record value differs from the independent replay.

    ``replayed`` maps pin id to the values the replay computed; only the pins
    it names are compared. The producer artifact is never read here, so this
    is the check that catches a record and an artifact agreeing with each
    other but differing from the source replay.
    """
    for pin, values in replayed.items():
        entry = entries.get(pin)
        if entry is None or entry.values != values:
            raise AssertionError("replay_value_mismatch")
    return True
