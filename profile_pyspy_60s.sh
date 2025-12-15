#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

MODE="${MODE:-record}"          # record|top|dump
DURATION="${DURATION:-60}"
RATE="${RATE:-100}"
FORMAT="${FORMAT:-flamegraph}"   # flamegraph|speedscope|raw|chrometrace
NONBLOCKING="${NONBLOCKING:-1}"  # 1=use --nonblocking, 0=blocking sampling
THREADS="${THREADS:-1}"          # 1=show thread ids in output, 0=off
FUNCTION="${FUNCTION:-1}"        # 1=record -F (aggregate by function's first line)
IDLE="${IDLE:-0}"                # 1=include idle threads
GIL="${GIL:-1}"                  # 1=only include traces holding GIL
NATIVE="${NATIVE:-0}"            # 1=include native stacks
SUBPROCESSES="${SUBPROCESSES:-0}" # 1=include subprocesses
DELAY="${DELAY:-1.0}"            # top refresh interval seconds

usage() {
  cat <<'EOF'
Usage:
  ./profile_pyspy_60s.sh [PID]

Environment variables:
  MODE=record        record|top|dump
  DURATION=60         seconds to sample
  RATE=100            samples per second
  FORMAT=flamegraph   flamegraph|speedscope|raw|chrometrace
  NONBLOCKING=1       1 to add --nonblocking
  THREADS=1           1 to add --threads
  FUNCTION=0          1 to add -F (record: aggregate by function)
  IDLE=0              1 to include idle threads
  GIL=0               1 to only include traces holding GIL
  NATIVE=0            1 to include native stacks
  SUBPROCESSES=0      1 to include subprocesses
  DELAY=1.0           (top) refresh interval seconds

Output:
  log/pyspy_<timestamp>.<ext>
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if ! command -v py-spy >/dev/null 2>&1; then
  echo "py-spy not found in PATH. Install with: python3 -m pip install -U py-spy" >&2
  exit 127
fi

PID="${1:-}"
if [[ -z "$PID" ]]; then
  # Prefer the main nonebot runner process. pgrep -n picks the newest matching PID.
  PID="$(pgrep -f -n 'python(3)?(\\.[0-9]+)? .* -m nb_cli run' || true)"
  [[ -n "$PID" ]] || PID="$(pgrep -f -n 'nb_cli run' || true)"
  [[ -n "$PID" ]] || PID="$(pgrep -f -n 'nonebot' || true)"
fi

if [[ -z "$PID" ]]; then
  echo "Could not auto-detect nonebot PID. You can pass it explicitly:" >&2
  echo "  ./profile_pyspy_60s.sh <PID>" >&2
  echo "
Candidate processes:" >&2
  ps -eo pid,ppid,user,cmd --sort=start_time | grep -E 'nb_cli run|nonebot|bot\.py' | grep -v grep | tail -n 30 >&2 || true
  exit 1
fi

mkdir -p log
TS="$(date +%Y%m%d_%H%M%S)"

echo "py-spy version: $(py-spy --version)"
echo "Target PID: $PID"

common_flags=()
[[ "$SUBPROCESSES" == "1" ]] && common_flags+=(--subprocesses)
[[ "$NONBLOCKING" == "1" ]] && common_flags+=(--nonblocking)
[[ "$GIL" == "1" ]] && common_flags+=(--gil)
[[ "$IDLE" == "1" ]] && common_flags+=(--idle)
[[ "$NATIVE" == "1" ]] && common_flags+=(--native)

case "$MODE" in
  dump)
    OUT="log/pyspy_dump_${TS}.txt"
    echo "Mode: dump (nonblocking=${NONBLOCKING}, subprocesses=${SUBPROCESSES}, native=${NATIVE})"
    set -x
    py-spy dump -p "$PID" "${common_flags[@]}" > "$OUT"
    set +x
    echo "Wrote: $OUT"
    ;;
  top)
    echo "Mode: top (rate=${RATE}, delay=${DELAY}, nonblocking=${NONBLOCKING}, threads are always shown in UI)"
    set -x
    py-spy top -p "$PID" -r "$RATE" --delay "$DELAY" "${common_flags[@]}"
    set +x
    ;;
  record)
    case "$FORMAT" in
      flamegraph) EXT="svg";;
      speedscope) EXT="json";;
      raw) EXT="raw";;
      chrometrace) EXT="json";;
      *)
        echo "Unknown FORMAT: $FORMAT (expected flamegraph|speedscope|raw|chrometrace)" >&2
        exit 2
        ;;
    esac

    OUT="log/pyspy_${TS}.${EXT}"
    args=(record -p "$PID" -o "$OUT" -d "$DURATION" -r "$RATE" -f "$FORMAT")
    [[ "$THREADS" == "1" ]] && args+=(--threads)
    [[ "$FUNCTION" == "1" ]] && args+=(-F)
    args+=("${common_flags[@]}")

    echo "Mode: record"
    echo "Sampling: ${RATE}Hz for ${DURATION}s (format=${FORMAT}, function=${FUNCTION}, nonblocking=${NONBLOCKING}, threads=${THREADS})"
    set -x
    py-spy "${args[@]}"
    set +x
    echo "Wrote: $OUT"
    ;;
  *)
    echo "Unknown MODE: $MODE (expected record|top|dump)" >&2
    exit 2
    ;;
esac
