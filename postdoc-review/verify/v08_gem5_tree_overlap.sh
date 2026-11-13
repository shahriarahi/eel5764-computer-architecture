#!/bin/bash
# V08 -- do the tracing extension and the two defense patches touch the same
# code?  Can the defense patch be applied to a clean tree at the paper's commit?
# Read-only (git apply --check modifies nothing).  Run inside WSL.
set -u
ROOT="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"
WT="$ROOT/.codex-tmp/aes-leakage-worktree"
PATCH="$WT/experiments/respq-defense-20261018/gem5-respq.patch"
TSPATCH="$WT/experiments/tdma/gem5-timeslot.patch"

echo "== the four trees (HEAD, modified files)"
for t in gem5 gem5-leak gem5-timeslot gem5-respq; do
  cd ~/eel5764/$t
  echo "   $t: HEAD $(git rev-parse --short HEAD), $(git status --porcelain | grep -c '^ M') modified, $(git status --porcelain | grep '^??' | grep -c 'src/') untracked under src/"
done

echo "== which tree holds which defense"
echo "   gem5-timeslot modified: $(cd ~/eel5764/gem5-timeslot && git status --porcelain | grep 'src/' | awk '{print $2}' | tr '\n' ' ')"
echo "   gem5-respq    modified: $(cd ~/eel5764/gem5-respq && git status --porcelain | grep 'src/' | awk '{print $2}' | tr '\n' ' ')"
echo "   gem5-respq has the time-slot code too: tdma_schedule.hh present: $(test -f ~/eel5764/gem5-respq/src/mem/tdma_schedule.hh && echo yes || echo no); tdma_slot_cycles in XBar.py: $(grep -c tdma_slot_cycles ~/eel5764/gem5-respq/src/mem/XBar.py); response_domain_prefixes in Cache.py: $(grep -c response_domain_prefixes ~/eel5764/gem5-respq/src/mem/cache/Cache.py)"

echo "== files of the tracing extension (lives in EXTRAS, outside every gem5 tree)"
ls "$WT/experiments/aes-leakage/gem5_ext" | sed 's/^/   /'
echo "   gem5-leak tree itself: $(cd ~/eel5764/gem5-leak && git status --porcelain | wc -l) changed files (0 = the tracing is entirely in EXTRAS)"

echo "== files touched by the stored defense patch (experiments/respq-defense-20261018/gem5-respq.patch)"
grep '^+++ ' "$PATCH" | sed 's/^+++ b\//   /'
echo "   overlap with the tracing extension's files (paths under gem5_ext/):"
for f in $(ls "$WT/experiments/aes-leakage/gem5_ext"); do
  if grep -q "^+++ .*gem5_ext/$f" "$PATCH"; then echo "   OVERLAP: $f"; fi
done
echo "   (no OVERLAP line above = no file in common)"

echo "== does the defense patch touch the code that calls the partition manager?"
echo "   stock call sites: $(cd ~/eel5764/gem5/src && grep -n 'partitionManager->' mem/cache/base.cc mem/cache/tags/base.cc mem/cache/tags/base_set_assoc.hh | tr '\n' ';')"
echo "   lines of the patch that mention partition: $(grep -c -i '^[+-].*partition' "$PATCH")"
echo "   base.cc hunks of the patch (old-file line ranges):"
awk '/^diff --git a\/src\/mem\/cache\/base.cc/ {on=1; next} /^diff --git/ {on=0} on && /^@@/ {print "     " $0}' "$PATCH" | cut -c1-70

echo "== the stored patch equals the live gem5-respq tree?"
cd ~/eel5764/gem5-respq
git diff > /tmp/v08_live.diff 2>/dev/null
echo "   tracked-file hunks: live tree $(grep -c '^@@' /tmp/v08_live.diff), stored patch (same files) $(for f in $(git status --porcelain | grep '^ M' | awk '{print $2}'); do awk -v f="$f" '$0 ~ "^diff --git a/"f {on=1; next} /^diff --git/ {on=0} on && /^@@/' "$PATCH"; done | wc -l)"
rm -f /tmp/v08_live.diff

echo "== git apply --check of the stored patch on a CLEAN tree at c8222cc (gem5-leak)"
cd ~/eel5764/gem5-leak
if git apply --check "$PATCH" 2>/tmp/v08_apply.err; then
  echo "   APPLIES CLEANLY (nothing was modified: --check only)"
else
  echo "   DOES NOT APPLY: $(head -3 /tmp/v08_apply.err)"
fi
echo "   gem5-leak still clean: $(git status --porcelain | wc -l) changed files"
rm -f /tmp/v08_apply.err
