#!/usr/bin/env bash
# Find a working Python 3.10+ interpreter and exec it with the given args.
#
# Neither "python" nor "python3" is reliably on PATH across platforms:
# modern macOS ships no "python" by default (only "python3", and only if
# Xcode CLT / Homebrew Python is installed), while Windows python.org
# installs typically provide "python" and "py" but not "python3". A single
# hardcoded interpreter name in .mcp.json/hooks.json therefore breaks one
# platform or the other. This shim tries every plausible candidate in order
# and execs the first one that actually works.
#
# On Windows + Git Bash, "python3" often resolves to the Microsoft Store stub
# at %LOCALAPPDATA%\Microsoft\WindowsApps\python3, which exits non-zero
# silently in non-TTY subprocess context. Probing each candidate with
# `-c ""` before trusting it skips that stub and falls through to the real
# python.org install ("python" in Git Bash) or the "py -3" launcher.
#
# Usage: resolve-python.sh <script.py> [args...]
set -e

# Git Bash / MSYS on Windows hands script paths to this shim in POSIX form
# (`/c/Users/...`). When we exec a Windows `python.exe`, it interprets a
# leading `/` as the current drive root, turning `/c/Users/...` into
# `C:\c\Users\...` and failing with ENOENT. Convert absolute path args to
# native Windows form first. `cygpath` is a Git Bash builtin, absent on
# macOS/Linux, where this is a no-op; `cygpath -w` is idempotent for
# already-Windows paths.
if command -v cygpath >/dev/null 2>&1; then
    converted=()
    for a in "$@"; do
        case "$a" in
            /*) converted+=("$(cygpath -w "$a")") ;;
            *)  converted+=("$a") ;;
        esac
    done
    set -- "${converted[@]}"
fi

probe() {
    # $1..N: the interpreter command (may be multi-word like `py -3`)
    # Writes "<major>.<minor>" to stdout and exits 0 iff at least Python 3.
    "$@" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null
}

# mcp>=1.2.0 requires Python >= 3.10.
is_compatible() {
    case "$1" in
        3.1[0-9]|3.[2-9][0-9]|[4-9].*|[1-9][0-9].*) return 0 ;;
        *) return 1 ;;
    esac
}

# Pass 1 — explicit minor-versioned binaries, highest first. Only present if
# the user explicitly installed them (Homebrew / python.org / pyenv).
for cmd in "python3.13" "python3.12" "python3.11" "python3.10"; do
    v=$(probe "$cmd") || continue
    if is_compatible "$v"; then
        exec "$cmd" "$@"
    fi
done

# Pass 2 — bare interpreters. Covers macOS/Linux ("python3") and Windows
# python.org installs ("python" / "py -3").
for cmd in "python3" "python" "py -3"; do
    # shellcheck disable=SC2086
    v=$(probe $cmd) || continue
    if is_compatible "$v"; then
        # shellcheck disable=SC2086
        exec $cmd "$@"
    fi
done

echo "auto-pilot: no working Python 3.10+ interpreter found." >&2
echo "  tried: python3.13, python3.12, python3.11, python3.10, python3, python, py -3" >&2
echo "  on Windows, install Python from https://python.org (NOT the Microsoft Store)" >&2
echo "  on macOS, install Python 3.10+ via Homebrew (\`brew install python\`)" >&2
exit 1
