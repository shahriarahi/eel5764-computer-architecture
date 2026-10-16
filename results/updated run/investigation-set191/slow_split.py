import struct, sys, json, numpy as np
from pathlib import Path
R = Path(sys.argv[1]); S = struct.Struct("<QIHH")
seeds = ["seed-5764a5e5","seed-5764a5e6","seed-5764a5e7"]
print("A  arm   | slow walks per 1000 (active/idle) | excess 20-100cyc act/idle | excess>100cyc act/idle | static sets excluded: always-slow")
for a in range(1,9):
    for arm, name in (("ctrl", f"UNPARTITIONED-A{a}"), ("trt ", f"{a}-{16-a}")):
        acc = np.zeros((2,2)); n = np.zeros(2); static = set()
        for sd in seeds:
            d = R/sd/name; b = (d/"probes.bin").read_bytes()
            m = np.array([S.unpack_from(b,i*16)[1] for i in range(16384)],float).reshape(64,256)
            L = np.array(json.loads((d/"run_meta.json").read_text())["contention"]["activity_labels"])
            fl = np.percentile(m,1); ex = m - fl
            always = (ex > 20).all(0); static |= set(np.where(always)[0].tolist())
            mm = ex[:, ~always]
            for lab in (0,1):
                rows = mm[L==lab]; n[lab] += rows.size
                acc[lab,0] += ((rows>20)&(rows<=100)).sum(); acc[lab,1] += (rows>100).sum()
        r = 1000*acc/n[:,None]
        print(f"{a}  {arm} | {r[1].sum():6.2f} / {r[0].sum():6.2f}              | {r[1,0]:6.2f} / {r[0,0]:6.2f}          | {r[1,1]:6.2f} / {r[0,1]:6.2f}        | {sorted(static)}")
