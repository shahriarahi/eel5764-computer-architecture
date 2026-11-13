"""Shared helpers for the aes-leakage tests.

Run from experiments/aes-leakage:
    python3 -B -m unittest discover -s tests -t .
Tests that need a tool that is not installed are skipped with a message that
names the missing tool; they never pass silently.
"""
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]      # experiments/aes-leakage
REPO = EXP.parents[1]                          # repository / worktree root
WORKLOADS = REPO / "workloads"
C_DIR = Path(__file__).resolve().parent / "c"

RISCV_CC = "riscv64-linux-gnu-gcc"
QEMU = "qemu-riscv64"
HOST_CC = "gcc"

# Must stay identical to workloads/build.sh (checked by test_build.py).
RISCV_CFLAGS = (
    "-O2 -march=rv64gc -mabi=lp64d -static -nostdlib -ffreestanding "
    "-fno-builtin -fno-tree-loop-distribute-patterns -Wall -Wextra "
    "-Wl,--no-relax"
).split()


def have(tool):
    return shutil.which(tool) is not None


def skip_unless_tool(*tools):
    missing = [t for t in tools if not have(t)]
    return unittest.skipIf(
        bool(missing),
        "SKIPPED: missing tool(s) %s (install them to run this test)" %
        ", ".join(missing))


def load_module(name, path):
    """Import a source file by path (avoids name clashes with repo packages)."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_analysis():
    return load_module("aes_leak_analysis_under_test",
                       EXP / "analysis" / "aes_leak_analysis.py")


def load_params():
    return load_module("leak_params_under_test", EXP / "leak_params.py")


def run(cmd, **kwargs):
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    return subprocess.run([str(c) for c in cmd], **kwargs)


def host_build(sources, out, defines=(), includes=()):
    """Compile a host program; returns the CompletedProcess."""
    cmd = [HOST_CC, "-O1", "-std=gnu17", "-Wall", "-Wextra"]
    cmd += ["-D%s" % d for d in defines]
    cmd += ["-I%s" % i for i in includes]
    cmd += ["-o", out] + [str(s) for s in sources]
    return run(cmd)


def riscv_build(sources, out, defines=(), includes=()):
    """Compile a freestanding RISC-V workload with the project flags."""
    cmd = [RISCV_CC] + RISCV_CFLAGS
    cmd += ["-D%s" % d for d in defines]
    cmd += ["-I%s" % i for i in includes]
    cmd += ["-o", str(out)] + [str(s) for s in sources]
    return run(cmd)


def tmpdir():
    return tempfile.TemporaryDirectory(prefix="aesleak-test-")


_FAKE_BUILDS = {}


def fake_clock_build(n_win):
    """Build all six workloads with -DLEAK_FAKE_CLOCK through build.sh.

    Cached per N_WIN for the whole test run.  These binaries only make sense
    under qemu-user: run_leakage.py refuses a manifest that lists
    LEAK_FAKE_CLOCK among its defines.
    """
    if n_win not in _FAKE_BUILDS:
        tmp = tmpdir()
        env = dict(os.environ, EXTRA_DEFS="-DLEAK_FAKE_CLOCK")
        proc = run(["sh", EXP / "build.sh", str(n_win), tmp.name], env=env)
        if proc.returncode != 0:
            raise AssertionError("build.sh failed:\n%s\n%s" %
                                 (proc.stdout, proc.stderr))
        _FAKE_BUILDS[n_win] = (tmp, Path(tmp.name))
    return _FAKE_BUILDS[n_win][1]


def qemu_run(binary, *args, timeout=300):
    return run([QEMU, binary] + [str(a) for a in args], timeout=timeout)
