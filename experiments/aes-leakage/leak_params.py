"""Read the experiment's schedule constants from leak_schedule.h.

leak_schedule.h is the single source of truth; this module only parses it, so
Python tooling cannot drift from the compiled workloads.  `overrides` carries
-D values given to the build (for example N_WIN=20) and is applied before the
derived offsets are evaluated.
"""
import re
from pathlib import Path

HEADER = Path(__file__).resolve().parent / "leak_schedule.h"

_DEFINE = re.compile(r"^\s*#\s*define\s+(\w+)(?:\s+(.*?))?\s*$")
_BYTES = re.compile(r"0x([0-9a-fA-F]{2})")
_INT_SUFFIX = re.compile(r"(?<=\d)[uUlL]+\b")
_IDENT = re.compile(r"[A-Za-z_]\w*")
_SAFE_EXPR = re.compile(r"^[0-9 +\-*()]*$")


def _strip_comment(text):
    text = re.sub(r"/\*.*?\*/", "", text)
    return re.sub(r"//.*$", "", text).strip()


def _read_defines(path=HEADER):
    """Map macro name -> replacement text (backslash continuations joined)."""
    defines = {}
    pending = None
    for raw in Path(path).read_text().splitlines():
        line = raw
        if pending is not None:
            line = pending + " " + line.strip()
            pending = None
        if line.rstrip().endswith("\\"):
            pending = line.rstrip()[:-1]
            continue
        match = _DEFINE.match(line)
        if match and match.group(2) is not None:
            defines.setdefault(match.group(1), _strip_comment(match.group(2)))
    return defines


def _evaluate(name, defines, overrides, depth=0):
    if name in overrides:
        return int(overrides[name])
    if depth > 8 or name not in defines:
        raise ValueError("cannot evaluate macro %r" % name)
    expression = _INT_SUFFIX.sub("", defines[name])

    def substitute(match):
        token = match.group(0)
        if token in overrides or token in defines:
            return str(_evaluate(token, defines, overrides, depth + 1))
        return token

    expression = _IDENT.sub(substitute, expression)
    if not _SAFE_EXPR.match(expression):
        raise ValueError("macro %r is not a plain integer expression: %r" %
                         (name, defines[name]))
    return int(eval(expression, {"__builtins__": {}}, {}))  # whitelisted


def _byte_list(text):
    return bytes(int(h, 16) for h in _BYTES.findall(text))


def parse_define_flags(flags):
    """Turn build flags like ['-DN_WIN=20', '-DLEAK_FAKE_CLOCK'] into a dict
    of integer overrides (flags without a numeric value are ignored)."""
    out = {}
    for flag in flags:
        match = re.fullmatch(r"-D(\w+)=(\d+)[uUlL]*", flag)
        if match:
            out[match.group(1)] = int(match.group(2))
    return out


def constants(overrides=None, path=HEADER):
    """All schedule constants as plain Python values."""
    overrides = dict(overrides or {})
    defines = _read_defines(path)
    result = {
        "T0": _evaluate("LEAK_T0", defines, overrides),
        "W": _evaluate("LEAK_W", defines, overrides),
        "OFF_PRIME": _evaluate("LEAK_OFF_PRIME", defines, overrides),
        "OFF_ENC": _evaluate("LEAK_OFF_ENC", defines, overrides),
        "OFF_ENC_END": _evaluate("LEAK_OFF_ENC_END", defines, overrides),
        "OFF_PROBE": _evaluate("LEAK_OFF_PROBE", defines, overrides),
        "N_WIN": _evaluate("LEAK_N_WIN", defines, overrides),
        "NSETS": _evaluate("LEAK_NSETS", defines, overrides),
    }
    result["KEY_HEX"] = _byte_list(defines["LEAK_KEY_INIT"]).hex()
    result["TVLA_FIXED_PT_HEX"] = _byte_list(
        defines["LEAK_TVLA_FIXED_PT_INIT"]).hex()
    return result
