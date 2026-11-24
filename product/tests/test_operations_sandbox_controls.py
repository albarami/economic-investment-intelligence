"""Real namespace, mount and launcher plants, on invented workspace paths."""

import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import sandbox_launch

ROOT = Path(__file__).resolve().parents[2]


def require_red(assertion):
    result = unittest.TestResult()
    unittest.FunctionTestCase(assertion).run(result)
    assert result.errors == [], "setup errors are not sandbox admission"
    assert len(result.failures) == 1
    assert "admitted" in result.failures[0][1]


def test_each_real_sandbox_control_admits_its_own_plant_only_when_disabled(tmp_path):
    private = tmp_path / "INVENTED-outside-mounts"
    private.mkdir()
    (private / "sentinel").write_text("INVENTED-only")
    cache, vault, stage = (
        tmp_path / name
        for name in ("INVENTED-input", "INVENTED-build", "INVENTED-stage")
    )
    for folder in (cache, vault, stage):
        folder.mkdir()
    layout = sandbox_launch.Layout(
        ROOT, cache, vault, ROOT / "data/engine_extensions", staging=stage
    )
    read = """
import sys
from pathlib import Path
try:
    assert Path(sys.argv[1]).read_text() == 'INVENTED-only'
except FileNotFoundError:
    print('blocked')
else:
    print('admitted')
"""

    def check(command):
        result = sandbox_launch.run_in_sandbox("build-release", layout, command)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "blocked", result.stdout

    read_command = (sys.executable, "-I", "-B", "-c", read, str(private / "sentinel"))
    check(read_command)
    original = sandbox_launch.build_argv

    def broaden_mount(*args, **kwargs):
        argv = original(*args, **kwargs)
        index = argv.index("--remount-ro")
        argv[index:index] = ["--ro-bind", str(private), str(private)]
        return argv

    with patch("sandbox_launch.build_argv", side_effect=broaden_mount):
        require_red(lambda: check(read_command))

    def bypass(profile, layout, command):
        return subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=5
        )

    with patch("sandbox_launch.run_in_sandbox", side_effect=bypass):
        require_red(lambda: check(read_command))

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        connect = """
import socket, sys
try:
    with socket.create_connection(('127.0.0.1', int(sys.argv[1])), timeout=1):
        pass
except ConnectionRefusedError:
    print('blocked')
else:
    print('admitted')
"""
        command = (sys.executable, "-I", "-B", "-c", connect, str(port))
        check(command)

        def omit_namespace(*args, **kwargs):
            argv = original(*args, **kwargs)
            argv.remove("--unshare-net")
            return argv

        with patch("sandbox_launch.build_argv", side_effect=omit_namespace):
            require_red(lambda: check(command))
