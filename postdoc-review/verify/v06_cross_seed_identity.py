"""V06 -- differential (non-interference) check on the FROZEN paper results.

Read-only.  For every allocation, compare the monitor's stored probes.bin
across the paper's three public plaintext seeds.  The monitor binary, its
arguments and the probe-path length are the same for the three seeds (checked
below), so a byte-identical file means the monitor's whole observation did not
depend on which plaintext stream the AES workload encrypted.

  sweep-v3  : unpartitioned controls and way partitioning only
  tdma-rsv  : full defense (way partitioning + request time slots + per-domain
              LLC response queues) and its stored unpartitioned controls
"""
import hashlib
import json

from _common import A, RESULTS, np

SEEDS = ("5764a5e5", "5764a5e6", "5764a5e7")
SPLITS = ["%d-%d" % (a, 16 - a) for a in range(1, 9)]
CONTROLS = ["UNPARTITIONED-A%d" % a for a in range(1, 9)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(path):
    return np.frombuffer(path.read_bytes(), dtype=A.PROBE_DTYPE)


def describe(sweep, case):
    paths = [RESULTS / sweep / ("seed-" + s) / case / "probes.bin" for s in SEEDS]
    if not all(p.is_file() for p in paths):
        return None
    hashes = [sha(p) for p in paths]
    recs = [records(p) for p in paths]
    ident = len(set(hashes)) == 1
    lat_diff = [int((recs[0]["latency"] != recs[k]["latency"]).sum())
                for k in (1, 2)]
    ts_diff = [int((recs[0]["timestamp"] != recs[k]["timestamp"]).sum())
               for k in (1, 2)]
    path_len = {len(str(p)) for p in paths}
    metas = []
    for s in SEEDS:
        m = RESULTS / sweep / ("seed-" + s) / case / "run_meta.json"
        metas.append(json.loads(m.read_text()) if m.is_file() else {})
    cmds = []
    for m in metas:
        cmd = [c for c in m.get("command_line", [])]
        if "--workload-seed" in cmd:
            cmd[cmd.index("--workload-seed") + 1] = "<seed>"
        cmds.append(tuple(cmd))
    return {"identical": ident, "hash0": hashes[0][:12],
            "n_records": len(recs[0]), "lat_diff": lat_diff, "ts_diff": ts_diff,
            "same_path_len": len(path_len) == 1,
            "same_cmd_except_seed": len(set(cmds)) == 1}


for sweep, label in (("tdma-rsv", "FULL DEFENSE sweep (tdma-rsv)"),
                     ("sweep-v3", "WAY PARTITIONING ONLY sweep (sweep-v3)")):
    print("== %s" % label)
    print("   case               identical across 3 seeds   records differing "
          "from seed 1 (latency) S2,S3   (timestamp) S2,S3   same cmd/path-len")
    summary = {"treat_ident": 0, "treat_n": 0, "ctrl_ident": 0, "ctrl_n": 0}
    for case in SPLITS + CONTROLS:
        d = describe(sweep, case)
        if d is None:
            print("   %-18s (not stored)" % case)
            continue
        kind = "treat" if case in SPLITS else "ctrl"
        summary[kind + "_n"] += 1
        summary[kind + "_ident"] += int(d["identical"])
        print("   %-18s %-26s %6d, %6d of %d        %6d, %6d     %s/%s" % (
            case, "YES (" + d["hash0"] + ")" if d["identical"] else "no",
            d["lat_diff"][0], d["lat_diff"][1], d["n_records"],
            d["ts_diff"][0], d["ts_diff"][1],
            d["same_cmd_except_seed"], d["same_path_len"]))
    print("   SUMMARY: partitioned/defended cases identical across seeds: %d of %d; "
          "unpartitioned controls identical: %d of %d\n" % (
              summary["treat_ident"], summary["treat_n"],
              summary["ctrl_ident"], summary["ctrl_n"]))
