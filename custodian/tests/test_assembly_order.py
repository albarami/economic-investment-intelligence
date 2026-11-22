"""Invented producer contracts; an execution trace is never release evidence."""

import hashlib

import pytest

from eii_custodian.publicdata.assembly import AssemblyError, Step, run_steps

# Plan r3, section 4 item 2. Grids and places belong to the single frame call.
# Main's S2-P64 register phase and S2-P63's pin phase both belong to this order.
ORDER = (
    "intake_evidence",
    "fetch_archive",
    "investment_capture",
    "reviewed_selections",
    "frame",
    "register_tables",
    "spine_graph",
    "additions",
    "gis_property_singles",
    "fsq",
    "series_stage",
    "heights",
    "trade_reconciliation",
    "busyness",
    "method_pins",
    "final_audit",
    "draw",
    "reports",
)


def steps_for(root, calls):
    def step(name):
        relative = name + ".json"

        def run():
            calls.append(name)
            body = ("syn-" + name).encode()
            (root / relative).write_bytes(body)
            return {relative: hashlib.sha256(body).hexdigest()}

        return Step(name, run, (relative,))

    return tuple(step(name) for name in ORDER)


def test_order_and_each_producer_once(tmp_path):
    calls = []
    trace = run_steps(tmp_path, steps_for(tmp_path, calls))
    assert trace == ORDER
    assert tuple(calls) == ORDER


@pytest.mark.parametrize("change", ["missing", "duplicate", "reordered", "unknown"])
def test_invalid_assembly_plan_refuses_before_any_producer(tmp_path, change):
    calls = []
    steps = list(steps_for(tmp_path, calls))
    if change == "missing":
        steps.pop()
    elif change == "duplicate":
        steps.append(steps[0])
    elif change == "reordered":
        steps[0], steps[1] = steps[1], steps[0]
    else:
        steps[0] = Step("syn_unknown", steps[0].run, steps[0].outputs)
    with pytest.raises(AssemblyError, match=r"^assembly_order_invalid$"):
        run_steps(tmp_path, tuple(steps))
    assert calls == []


@pytest.mark.parametrize("phase", ORDER)
@pytest.mark.parametrize("defect", ["missing", "unreported", "extra", "wrong_hash"])
def test_missing_or_incorrect_output_stops_before_next_phase(tmp_path, phase, defect):
    calls = []
    steps = list(steps_for(tmp_path, calls))
    position = ORDER.index(phase)
    original = steps[position]

    def bad():
        result = dict(original.run())
        path = tmp_path / original.outputs[0]
        if defect == "missing":
            path.unlink()
        elif defect == "unreported":
            result.clear()
        elif defect == "extra":
            result["syn_extra.json"] = "a" * 64
        else:
            path.write_bytes(b"syn-substituted")
        return result

    steps[position] = Step(phase, bad, original.outputs)
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        run_steps(tmp_path, tuple(steps))
    assert tuple(calls) == ORDER[: position + 1]


@pytest.mark.parametrize("name", ["../syn_escape", "/syn_absolute", "", "."])
def test_unsafe_declared_output_refuses_before_any_call(tmp_path, name):
    calls = []
    steps = list(steps_for(tmp_path, calls))
    steps[-1] = Step("reports", steps[-1].run, (name,))
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        run_steps(tmp_path, tuple(steps))
    assert calls == []


@pytest.mark.parametrize("within_step", [False, True])
def test_two_producers_cannot_own_the_same_output(tmp_path, within_step):
    calls = []
    steps = list(steps_for(tmp_path, calls))
    outputs = (steps[0].outputs[0],)
    if within_step:
        outputs *= 2
    steps[-1] = Step("reports", steps[-1].run, outputs)
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        run_steps(tmp_path, tuple(steps))
    assert calls == []


def test_symlink_output_is_not_followed_outside_root(tmp_path):
    root = tmp_path / "syn-root"
    root.mkdir()
    outside = tmp_path / "syn-outside"
    outside.write_bytes(b"syn")
    calls = []
    steps = list(steps_for(root, calls))
    original = steps[0]

    def bad():
        calls.append(original.name)
        (root / original.outputs[0]).symlink_to(outside)
        return {original.outputs[0]: hashlib.sha256(b"syn").hexdigest()}

    steps[0] = Step(original.name, bad, original.outputs)
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        run_steps(root, tuple(steps))
    assert calls == [ORDER[0]]


def test_producer_failure_propagates_without_running_later_steps(tmp_path):
    calls = []
    steps = list(steps_for(tmp_path, calls))

    def refused():
        calls.append("intake_evidence")
        raise ValueError("syn-refused")

    steps[0] = Step("intake_evidence", refused, steps[0].outputs)
    with pytest.raises(ValueError, match=r"^syn-refused$"):
        run_steps(tmp_path, tuple(steps))
    assert calls == [ORDER[0]]


def test_output_hash_must_be_a_sha256_string(tmp_path):
    calls = []
    steps = list(steps_for(tmp_path, calls))
    original = steps[0]

    def bad():
        original.run()
        return {original.outputs[0]: "syn-not-a-hash"}

    steps[0] = Step(original.name, bad, original.outputs)
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        run_steps(tmp_path, tuple(steps))
    assert calls == [ORDER[0]]


def test_declared_output_in_symlink_folder_refuses_before_any_call(tmp_path):
    root = tmp_path / "syn-root"
    root.mkdir()
    (root / "syn-link").symlink_to(tmp_path, target_is_directory=True)
    calls = []
    steps = list(steps_for(root, calls))
    steps[-1] = Step("reports", steps[-1].run, ("syn-link/report.json",))
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        run_steps(root, tuple(steps))
    assert calls == []


def test_read_only_phases_may_declare_no_files(tmp_path):
    calls = []
    steps = list(steps_for(tmp_path, calls))

    def reviewed():
        calls.append("reviewed_selections")
        return {}

    steps[3] = Step("reviewed_selections", reviewed, ())
    assert run_steps(tmp_path, tuple(steps)) == ORDER
    assert tuple(calls) == ORDER


def test_non_mapping_producer_result_is_a_closed_refusal(tmp_path):
    calls = []
    steps = list(steps_for(tmp_path, calls))

    def bad():
        calls.append("intake_evidence")
        return None

    steps[0] = Step("intake_evidence", bad, steps[0].outputs)
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        run_steps(tmp_path, tuple(steps))
    assert calls == [ORDER[0]]


def test_output_read_error_is_a_closed_refusal(tmp_path, monkeypatch):
    from eii_custodian.publicdata import assembly

    calls = []
    steps = steps_for(tmp_path, calls)

    def unreadable(path):
        raise OSError("SYN-upstream-diagnostic")

    monkeypatch.setattr(assembly, "file_hash", unreadable)
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        run_steps(tmp_path, steps)
    assert calls == [ORDER[0]]
