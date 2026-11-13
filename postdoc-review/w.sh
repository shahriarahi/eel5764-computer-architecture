#!/bin/bash
# w.sh -- run ONE command line inside WSL (Ubuntu-26.04), starting in the
# experiment directory.  Call it from Git Bash (the Bash tool) on Windows:
#
#   bash "/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/w.sh" '<command>'
#
# Put the command in SINGLE quotes so that Git Bash does not expand $HOME, ~ or
# $(...) before WSL sees them.  The command is written to a temporary script,
# which avoids every nested-quoting problem.  Exit status = the command's.
set -u
if [ "$#" -ne 1 ]; then
    echo "usage: bash w.sh '<command to run in WSL from experiments/aes-leakage>'" >&2
    exit 64
fi
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$HERE/exec"
TMP="$HERE/exec/.wcmd.$$.$RANDOM.sh"
{
    printf '%s\n' 'export PYTHONDONTWRITEBYTECODE=1'
    printf '%s\n' 'cd "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage" || exit 97'
    printf '%s\n' "$1"
} > "$TMP"
WIN_TMP=$(cd "$HERE/exec" && pwd -W 2>/dev/null || pwd)
BASE=$(basename "$TMP")
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-26.04 -e bash -l "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/exec/$BASE"
STATUS=$?
rm -f "$TMP"
exit $STATUS
