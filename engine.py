"""CLI: explicit JSON input -> astrological JSON output, no registry or service."""
import argparse
import json
from pathlib import Path
import sys

from astro_engine import calculate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="UTF-8 JSON path, or - for stdin")
    parser.add_argument("--output", help="New JSON file (existing files are never overwritten)")
    args = parser.parse_args(argv)
    try:
        if args.output and Path(args.output).exists():
            raise ValueError("Output already exists; choose another path.")
        source = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8-sig")
        payload = json.loads(source)
        result = json.dumps(calculate(payload), ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            with Path(args.output).open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(result + "\n")
        else:
            print(result)
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
        print(f"Calculation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
