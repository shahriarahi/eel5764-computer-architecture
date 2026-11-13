#!/bin/bash
# V14 -- the batch launcher and the deviation logger, tested in the mirror.
# gem5 is NOT run: a FAKE gem5 (a 10-line shell script under a temporary HOME)
# stands in for it, so that run_arm.sh / run_batch.sh are exercised end to end
# (parallel start, summary log, failure detection, refusal to reuse a name).
# Needs the mirror and builds made by V10 and V12.  Run inside WSL.
set -u
export PYTHONDONTWRITEBYTECODE=1
ROOT="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"
REF="$ROOT/postdoc-review/reference"
MIR="$ROOT/postdoc-review/verify/_tmp/mirror"
E="$MIR/experiments/aes-leakage"
[ -d "$E/build/ovl-n2000" ] || { echo "run v10 and v12 first"; exit 1; }
cp "$REF/run_arm.sh" "$REF/run_batch.sh" "$E/"; rm -rf "$E/batches"; cp -r "$REF/batches" "$E/"
cd "$E"
rm -rf runs/e1-* runs/e2-* runs/e3-* runs/*.batch.log runs/*.launch.log

echo "== (1) dry run of every batch file (pre-flight only)"
for b in e1-diff e1-full e2-main e2-explore e3-defense; do
  DRY_RUN=1 bash run_batch.sh batches/$b.txt > "$MIR/b.out" 2>&1
  echo "   $b: exit $? | $(grep -c 'DRY RUN (' "$MIR/b.out") command(s) | $(tail -1 "$MIR/b.out")"
done

echo "== (2) the launchers end to end with a FAKE gem5 (no simulation)"
FAKEHOME="$MIR/fakehome"; rm -rf "$FAKEHOME"
for t in gem5-leak gem5-leak-def; do
  mkdir -p "$FAKEHOME/eel5764/$t/build/RISCV"
  cat > "$FAKEHOME/eel5764/$t/build/RISCV/gem5.opt" <<'EOF'
#!/bin/bash
# FAKE gem5 for testing the launch scripts only.
while [ "$#" -gt 0 ]; do [ "$1" = "-d" ] && OUT=$2; shift; done
mkdir -p "$OUT"; sleep 1
echo "victim aes_self_test=PASS" > "$OUT/simout.txt"
case "$OUT" in
  *c1-s2*) echo "monitor error=prime_deadline window=1" >> "$OUT/simout.txt"; exit 0 ;;
  *) echo "monitor status=PASS records=128000" >> "$OUT/simout.txt" ;;
esac
EOF
  chmod +x "$FAKEHOME/eel5764/$t/build/RISCV/gem5.opt"
done
START=$(date +%s)
HOME="$FAKEHOME" bash run_batch.sh batches/e1-diff.txt 4 > "$MIR/b.out" 2>&1; STATUS=$?
END=$(date +%s)
echo "   batch e1-diff with one injected deadline error: exit $STATUS (expected 1), $((END - START)) s for 10 one-second fake runs at 4 in parallel"
sed 's/^/     /' runs/e1-diff.batch.log
echo "   launch logs written: $(ls runs/*.launch.log | wc -l); run directories: $(ls -d runs/e1-* | grep -v -c '\.')"
HOME="$FAKEHOME" bash run_batch.sh batches/e1-diff.txt 4 > "$MIR/b.out" 2>&1
echo "   second start of the same batch: exit $? (expected 3) | $(tail -1 "$MIR/b.out")"
HOME="$FAKEHOME" bash run_batch.sh batches/e1-full.txt 2 > "$MIR/b.out" 2>&1
echo "   batch e1-full, all fake runs pass: exit $? | $(tail -1 "$MIR/b.out")"
HOME="$FAKEHOME" bash run_arm.sh e3-od8-s1-n2000 r1-scrub ovl-n2000 8-8 8 1466213861 defense > "$MIR/b.out" 2>&1
echo "   single defense-mode run through run_arm.sh: exit $? | $(tail -1 "$MIR/b.out")"
rm -rf runs/e1-* runs/e2-* runs/e3-* runs/*.batch.log runs/*.launch.log "$FAKEHOME" "$MIR/b.out"

echo "== (3) log_deviations.py"
cp "$ROOT/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage/PREREGISTRATION_DRAFT.md" "$ROOT/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage/progress.md" "$E/"
BEFORE=$(wc -l < PREREGISTRATION_DRAFT.md)
python3 -B "$REF/log_deviations.py" "$E" D1 D2 D3; echo "   exit $?"
python3 -B "$REF/log_deviations.py" "$E" D2; echo "   logging D2 a second time: exit $? (expected nonzero)"
python3 -B "$REF/log_deviations.py" "$E" D4; echo "   exit $?"
python3 -B "$REF/log_deviations.py" "$E" D9; echo "   unknown deviation: exit $? (expected nonzero)"
echo "   PREREGISTRATION_DRAFT.md: $BEFORE -> $(wc -l < PREREGISTRATION_DRAFT.md) lines; the first $BEFORE lines unchanged: $(head -n "$BEFORE" PREREGISTRATION_DRAFT.md | cmp -s - "$ROOT/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage/PREREGISTRATION_DRAFT.md" && echo yes || echo NO)"
echo "   deviation bullets now in the preregistration: $(grep -c '^\* \*\*D[0-9] (' PREREGISTRATION_DRAFT.md) (D0..D4); in progress.md: $(grep -c '^\* \*\*D[0-9] (' progress.md); DATE_LOGGED left: $(grep -c DATE_LOGGED PREREGISTRATION_DRAFT.md progress.md | tr '\n' ' ')"
grep -o '^\* \*\*D[0-9] ([0-9-]*' PREREGISTRATION_DRAFT.md | tr '\n' ';'; echo
cp "$REF/docs/PREREGISTRATION_OVERLAP.md" "$E/"
echo "== (4) whole suite in the mirror with the ledgers extended (the documentation tests read these files)"
python3 -B -m unittest discover -s tests -t . 2>&1 | tail -3
