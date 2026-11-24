"""Linux x86-64 syscall tripwire for this task's invented process tree.

Observe attempts before the kernel executes them, including native libraries,
threads and exec'd descendants. Denied calls return EPERM even if the child
catches it; the parent retains the attempt and fails its independent assertion.
No provider is contacted to prove the tripwire. This is test tooling only.
Only successful binds by this process tree own Internet ports; Unix destinations
must resolve within the trace's scratch root. This catches accidental attempts,
not an adversary racing a sibling's sockaddr write against the kernel copy.
"""

from __future__ import annotations

import ctypes
import errno
import ipaddress
import json
import os
import signal
import socket
from collections.abc import Sequence
from pathlib import Path
from typing import Any

LIBC = ctypes.CDLL(None, use_errno=True)
LIBC.ptrace.restype = ctypes.c_long
LIBC.ptrace.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
TRACEME, PEEKDATA, GETREGS, SETREGS, SYSCALL, SETOPTIONS = 0, 2, 12, 13, 24, 0x4200
OPTIONS = 1 | 2 | 4 | 8 | 16 | 0x100000  # syscall/fork/vfork/clone/exec/exitkill
WALL = 0x40000000
NETWORK_CALLS = frozenset({41, 42, 44, 46, 49, 50, 53, 56, 307, 425, 426, 427, 435})


class Registers(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_ulonglong)
        for name in (
            "r15 r14 r13 r12 rbp rbx r11 r10 r9 r8 rax rcx rdx rsi rdi "
            "orig_rax rip cs eflags rsp ss fs_base gs_base ds es fs gs"
        ).split()
    ]


def ptrace(request: int, pid: int, address: Any = None, data: Any = None) -> int:
    ctypes.set_errno(0)
    result = LIBC.ptrace(request, pid, address, data)
    code = ctypes.get_errno()
    if result == -1 and code:
        raise OSError(code, "INVENTED-tripwire-ptrace-failed")
    return int(result)


def memory(pid: int, address: int, size: int) -> bytes:
    value = bytearray()
    for offset in range(0, size, ctypes.sizeof(ctypes.c_long)):
        word = ptrace(PEEKDATA, pid, address + offset)
        value.extend(ctypes.c_ulonglong(word).value.to_bytes(8, "little"))
    return bytes(value[:size])


def outbound(
    pid: int,
    address: int,
    size: int,
    scratch: Path,
    ports: set[tuple[int, str, int]],
    *,
    binding: bool = False,
) -> str | None:
    if not address:
        return None
    raw = memory(pid, address, min(size, 110))
    if len(raw) < 2:
        return "connect"
    family = int.from_bytes(raw[:2], "little")
    if family == socket.AF_UNSPEC:
        # connect(AF_UNSPEC) disconnects UDP, but bind(AF_UNSPEC, ANY)
        # creates a wildcard listener address on Linux.
        return "connect" if binding else None
    if family == socket.AF_UNIX:
        name = raw[2:].split(b"\0", 1)[0]
        if not name:
            return "unix-relay"  # Includes every abstract-namespace endpoint.
        path = Path(os.fsdecode(name))
        if not path.is_absolute():
            path = Path(f"/proc/{pid}/cwd").resolve() / path
        return None if path.resolve().is_relative_to(scratch) else "unix-relay"
    # Bubblewrap configures the isolated loopback interface through local
    # kernel routing IPC. This is not an Internet endpoint. Only kernel PID
    # zero with no multicast groups is allowed as a netlink destination.
    if family == socket.AF_NETLINK and len(raw) >= 12:
        if binding:
            return "connect" if raw[8:12] != bytes(4) else None
        return "connect" if raw[4:12] != bytes(8) else None
    if family in {socket.AF_INET, socket.AF_INET6} and len(raw) >= 4:
        port = int.from_bytes(raw[2:4], "big")
        if port == 53:
            return "dns"
    if family == socket.AF_INET and len(raw) >= 8:
        host = str(ipaddress.IPv4Address(raw[4:8]))
    elif family == socket.AF_INET6 and len(raw) >= 24:
        ip = ipaddress.IPv6Address(raw[8:24])
        host = str(ip.ipv4_mapped or ip)
    else:
        return "connect"
    if host not in {"127.0.0.1", "::1"}:
        return "connect"
    return None if binding or endpoint(pid, host, port) in ports else "connect"


def endpoint(pid: int, host: str, port: int) -> tuple[int, str, int]:
    # Binding inside the build sandbox does not own a host-namespace relay.
    return Path(f"/proc/{pid}/ns/net").stat().st_ino, host, port


def socket_name(pid: int, fd: int) -> tuple[int, Any]:
    """Read the stopped tracee's kernel socket; never infer an implicit bind."""
    status = Path(f"/proc/{pid}/status").read_text()
    tgid = next(
        int(line.split()[1]) for line in status.splitlines() if line.startswith("Tgid:")
    )
    # pidfd_open takes a thread-group leader on the pinned kernel. Worker
    # threads share that group's descriptor table, including this socket.
    descriptor = os.pidfd_open(tgid)
    try:
        duplicate = LIBC.syscall(438, descriptor, fd, 0)  # pidfd_getfd, x86-64
        if duplicate == -1:
            raise OSError(
                ctypes.get_errno(), "INVENTED-tripwire-socket-inspection-failed"
            )
        with socket.socket(fileno=duplicate) as channel:
            return channel.family, channel.getsockname()
    finally:
        os.close(descriptor)


def network_call(
    pid: int, regs: Registers, scratch: Path, ports: set[tuple[int, str, int]]
) -> str | None:
    number = regs.orig_rax
    if number == 56 and regs.rdi & 0x800000:
        return "untraced-child-refused"
    if number == 435 and int.from_bytes(memory(pid, regs.rdi, 8), "little") & 0x800000:
        return "untraced-child-refused"
    if number == 53 and regs.rdi != socket.AF_UNIX:
        return "unsupported-socketpair"
    if number in {42, 49}:  # connect / bind (non-loopback bind is forbidden too)
        return outbound(pid, regs.rsi, regs.rdx, scratch, ports, binding=number == 49)
    if number == 50:  # listen without bind would implicitly bind every interface.
        family, name = socket_name(pid, regs.rdi)
        if family == socket.AF_UNIX:
            return None
        if family in {socket.AF_INET, socket.AF_INET6}:
            ip = ipaddress.ip_address(name[0])
            host = (
                str(ip.ipv4_mapped or ip)
                if isinstance(ip, ipaddress.IPv6Address)
                else str(ip)
            )
            if host in {"127.0.0.1", "::1"} and endpoint(pid, host, name[1]) in ports:
                return None
        return "listen"
    if number == 44:  # sendto, including DNS/UDP without connect
        attempt = outbound(pid, regs.r8, regs.r9, scratch, ports)
        return "sendto" if attempt == "connect" else attempt
    if number in {46, 307}:  # sendmsg / sendmmsg; native msghdr, mmsghdr stride
        count = 1 if number == 46 else regs.rdx
        for index in range(count):
            header = memory(pid, regs.rsi + index * 64, 12)
            address = int.from_bytes(header[:8], "little")
            size = int.from_bytes(header[8:12], "little")
            attempt = outbound(pid, address, size, scratch, ports)
            if attempt is not None:
                return (
                    ("sendmsg" if number == 46 else "sendmmsg")
                    if attempt == "connect"
                    else attempt
                )
    # Refuse alternate ABI/asynchronous/raw transports rather than leave an
    # unobserved network path. The task does not need any of these facilities.
    if number & 0x40000000 or number in {425, 426, 427}:
        return "unsupported-network-transport"
    if (
        number == 41
        and regs.rdi == socket.AF_NETLINK
        and regs.rdx == 0
        and regs.rsi & 0xF in {socket.SOCK_RAW, socket.SOCK_DGRAM}
    ):
        return None
    if number == 41 and (
        regs.rdi not in {socket.AF_UNIX, socket.AF_INET, socket.AF_INET6}
        or regs.rsi & 0xF not in {socket.SOCK_STREAM, socket.SOCK_DGRAM}
    ):
        return "unsupported-socket"
    return None


def trace(command: Sequence[str], scratch: Path) -> tuple[int, list[str], str]:
    if os.uname().machine != "x86_64":
        raise AssertionError("network tripwire requires the pinned Linux x86-64 runner")
    if not scratch.is_dir():
        raise AssertionError("network tripwire requires its documented temporary root")
    # Anonymous capture keeps exception paths out of files and cannot fill a
    # pipe while the tracer waits for a stopped descendant.
    output = os.memfd_create("INVENTED-network-tripwire", os.MFD_CLOEXEC)
    try:
        reader, writer = os.pipe()
        try:
            tracer = os.fork()
        except BaseException:
            os.close(reader)
            os.close(writer)
            raise
        if tracer == 0:
            os.close(reader)
            try:
                try:
                    result: Any = _trace(command, output, scratch.resolve())
                except BaseException as error:
                    result = dict(
                        error="OSError"
                        if isinstance(error, OSError)
                        else "AssertionError",
                        args=error.args,
                    )
                with os.fdopen(writer, "w") as stream:
                    json.dump(result, stream)
            finally:
                os._exit(0)
        os.close(writer)
        try:
            # Drain before waiting: captured output can exceed pipe capacity.
            with os.fdopen(reader) as stream:
                payload = stream.read()
        finally:
            _, status = os.waitpid(tracer, 0)
        if status != 0:
            raise AssertionError("network tripwire tracer failed")
        result = json.loads(payload)
        if isinstance(result, dict):
            if result["error"] == "OSError":
                raise OSError(*result["args"])
            raise AssertionError(*result["args"])
        code, attempts, captured = result
        return code, attempts, captured
    finally:
        os.close(output)


def _trace(
    command: Sequence[str], output: int, scratch: Path
) -> tuple[int, list[str], str]:
    pid = os.fork()
    if pid == 0:
        try:
            os.dup2(output, 1)
            os.dup2(output, 2)
            os.close(output)
            ptrace(TRACEME, 0)
            os.kill(os.getpid(), signal.SIGSTOP)
            env = {
                k: v for k, v in os.environ.items() if k in {"PATH", "LANG", "LC_ALL"}
            }
            # Python's user-site expansion otherwise asks NSS/nscd for a home.
            # Supply invented local identity so it needs no resolver relay.
            env.update(
                HOME=str(scratch), USER="INVENTED-runner", LOGNAME="INVENTED-runner"
            )
            os.execve(command[0], list(command), env)
        except BaseException:
            os._exit(125)
    owned = {pid}
    attempts: list[str] = []
    denied: set[int] = set()
    binding: dict[int, int] = {}
    ports: set[tuple[int, str, int]] = set()
    finished: set[int] = set()
    exit_code = 125
    try:
        _, status = os.waitpid(pid, 0)
        if os.WIFEXITED(status) or os.WIFSIGNALED(status):
            owned.discard(pid)
        if not os.WIFSTOPPED(status) or os.WSTOPSIG(status) != signal.SIGSTOP:
            raise AssertionError("network tripwire failed before tracing")
        ptrace(SETOPTIONS, pid, None, OPTIONS)
        ptrace(SYSCALL, pid)
        while owned:
            child, status = os.waitpid(-1, WALL)
            if os.WIFEXITED(status) or os.WIFSIGNALED(status):
                owned.discard(child)
                finished.add(child)
                if child == pid:
                    exit_code = os.waitstatus_to_exitcode(status)
                continue
            owned.add(child)
            finished.discard(child)
            stopped = os.WSTOPSIG(status)
            event = status >> 16
            deliver = 0
            if stopped == signal.SIGTRAP | 0x80:
                info = (ctypes.c_ubyte * 88)()
                size = ptrace(0x420E, child, ctypes.sizeof(info), ctypes.byref(info))
                if size < 24 or info[0] not in {1, 2}:
                    raise AssertionError(
                        "network tripwire cannot classify syscall stop"
                    )
                if info[0] == 1:
                    arch = int.from_bytes(bytes(info[4:8]), "little")
                    number = int.from_bytes(bytes(info[24:32]), "little")
                    attempt = None
                    if arch != 0xC000003E:
                        attempt = "unsupported-syscall-abi"
                    elif number in NETWORK_CALLS or number & 0x40000000:
                        regs = Registers()
                        regs.orig_rax = number
                        for index, name in enumerate(
                            ("rdi", "rsi", "rdx", "r10", "r8", "r9")
                        ):
                            setattr(
                                regs,
                                name,
                                int.from_bytes(
                                    bytes(info[32 + index * 8 : 40 + index * 8]),
                                    "little",
                                ),
                            )
                        attempt = network_call(child, regs, scratch, ports)
                        if number == 49 and attempt is None:
                            binding[child] = regs.rdi
                    if attempt is not None:
                        attempts.append(attempt)
                        regs = Registers()
                        ptrace(GETREGS, child, None, ctypes.byref(regs))
                        regs.orig_rax = ctypes.c_ulonglong(-1).value
                        denied.add(child)
                        ptrace(SETREGS, child, None, ctypes.byref(regs))
                elif child in denied:
                    regs = Registers()
                    ptrace(GETREGS, child, None, ctypes.byref(regs))
                    regs.rax = ctypes.c_ulonglong(-errno.EPERM).value
                    ptrace(SETREGS, child, None, ctypes.byref(regs))
                    denied.remove(child)
                elif child in binding:
                    fd = binding.pop(child)
                    if int.from_bytes(bytes(info[24:32]), "little", signed=True) == 0:
                        family, name = socket_name(child, fd)
                        if family in {socket.AF_INET, socket.AF_INET6}:
                            ip = ipaddress.ip_address(name[0])
                            host = (
                                str(ip.ipv4_mapped or ip)
                                if isinstance(ip, ipaddress.IPv6Address)
                                else str(ip)
                            )
                            ports.add(endpoint(child, host, name[1]))
            elif event in {1, 2, 3}:
                new_pid = ctypes.c_ulonglong()
                ptrace(0x4201, child, None, ctypes.byref(new_pid))
                if new_pid.value not in finished:
                    owned.add(new_pid.value)
            elif stopped not in {signal.SIGSTOP, signal.SIGTRAP}:
                deliver = stopped
            ptrace(SYSCALL, child, None, deliver)
    finally:
        for child in owned:
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass
        while True:
            try:
                os.waitpid(-1, WALL)
            except ChildProcessError:
                break
    size = os.fstat(output).st_size
    if size > 16 * 1024 * 1024:
        raise AssertionError("network tripwire output exceeds its evidence bound")
    return exit_code, attempts, os.pread(output, size, 0).decode()
