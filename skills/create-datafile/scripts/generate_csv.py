"""
Generate a CSV data file for CSV-driven test cases (e.g. performance load-test
steps that reference {{data.<file>.<column>}}).

Usage:
  # swagger-driven — columns auto-detected from an endpoint's request_fields,
  # read from the swagger-spec.endpoints.json companion file the
  # analyze-requirements skill's fetch_swagger.py script already produces:
  python generate_csv.py --endpoints swagger-spec.endpoints.json \
      --method POST --path /api/orders --rows 50 --output ord_load1.csv

  # manual columns — no swagger source at all:
  python generate_csv.py --columns "customerId,sku,quantity" --rows 50 --output ord_load1.csv

  # swagger-driven with overrides (--columns replaces the auto-detected set
  # entirely; --add appends synthetic columns; --remove drops named columns;
  # applied in that order):
  python generate_csv.py --endpoints swagger-spec.endpoints.json \
      --method POST --path /api/orders --rows 50 --output ord_load1.csv \
      --add "region:enum:us,eu,apac" --remove "internalFlag"

This script only GENERATES the data — it does not validate its own output.
The calling skill must read the CSV back and validate it (header/row count/
required-field completeness/type plausibility) before uploading; see
skills/create-datafile/SKILL.md.
"""
import argparse
import csv
import json
import random
import re
import string
import sys
import uuid
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Column spec: {"name": str, "type": str|None, "format": str|None,
#               "enum": list|None, "minLength": int|None, "maxLength": int|None,
#               "minimum": number|None, "maximum": number|None, "required": bool}
# ---------------------------------------------------------------------------

def load_endpoint_fields(endpoints_path, method, path):
    with open(endpoints_path, encoding="utf-8") as f:
        endpoints = json.load(f)
    for entry in endpoints:
        if entry.get("method", "").upper() == method.upper() and entry.get("path") == path:
            return entry.get("request_fields", [])
    raise ValueError(
        f"No entry for {method.upper()} {path} found in {endpoints_path}. "
        f"Available: {[(e.get('method'), e.get('path')) for e in endpoints]}"
    )


def parse_add_spec(spec):
    """Parse '<name>:<type>[:enumval1,enumval2,...]' into a column dict."""
    parts = spec.split(":")
    name = parts[0]
    field_type = parts[1] if len(parts) > 1 else "string"
    column = {"name": name, "type": field_type, "required": False}
    if field_type == "enum" and len(parts) > 2:
        column["enum"] = parts[2].split(",")
        column["type"] = "string"
    return column


def build_column_set(args):
    columns = []
    if args.endpoints and args.method and args.path:
        columns = [
            {
                "name": f["name"],
                "type": f.get("type", "string"),
                "format": f.get("format"),
                "enum": f.get("enum"),
                "minLength": f.get("minLength"),
                "maxLength": f.get("maxLength"),
                "minimum": f.get("minimum"),
                "maximum": f.get("maximum"),
                "pattern": f.get("pattern"),
                "required": bool(f.get("required")),
            }
            for f in load_endpoint_fields(args.endpoints, args.method, args.path)
        ]

    if args.columns:
        # Replaces the set entirely -- keep any matching metadata from the
        # auto-detected set (so a name-only override still gets real
        # constraints), else fall back to a plain string column.
        by_name = {c["name"]: c for c in columns}
        columns = [
            by_name.get(name.strip(), {"name": name.strip(), "type": "string", "required": False})
            for name in args.columns.split(",")
        ]

    for add_spec in args.add or []:
        columns.append(parse_add_spec(add_spec))

    if args.remove:
        remove_names = {n.strip() for n in args.remove.split(",")}
        columns = [c for c in columns if c["name"] not in remove_names]

    if not columns:
        raise ValueError(
            "No columns to generate — provide --endpoints/--method/--path, and/or --columns/--add."
        )
    return columns


# ---------------------------------------------------------------------------
# Value synthesis
# ---------------------------------------------------------------------------

_UNSYNTHESIZABLE_NOTES = []


def _random_string(min_len, max_len):
    length = random.randint(min_len, max_len)
    return "".join(random.choices(string.ascii_lowercase, k=length))


def synthesize_value(column, row_index):
    name = column["name"]
    field_type = (column.get("type") or "string").lower()
    fmt = (column.get("format") or "").lower()
    enum = column.get("enum")

    if enum:
        return random.choice(enum)

    if column.get("pattern"):
        _UNSYNTHESIZABLE_NOTES.append(
            f"{name}: has a 'pattern' constraint — generated as a plain string, verify it satisfies the pattern"
        )

    if fmt == "email":
        return f"user{row_index}.{uuid.uuid4().hex[:6]}@example.com"
    if fmt == "uuid":
        return str(uuid.uuid4())
    if fmt in ("date", "date-time"):
        d = datetime(2026, 1, 1) + timedelta(days=row_index)
        return d.strftime("%Y-%m-%d") if fmt == "date" else d.strftime("%Y-%m-%dT%H:%M:%SZ")

    if field_type in ("integer", "number"):
        lo = column.get("minimum")
        hi = column.get("maximum")
        lo = 1 if lo is None else int(lo)
        hi = lo + 1000 if hi is None else int(hi)
        value = random.randint(lo, hi)
        return value if field_type == "integer" else float(value)

    if field_type == "boolean":
        return random.choice([True, False])

    # default: string
    min_len = column.get("minLength") or 4
    max_len = column.get("maxLength") or max(min_len + 6, 12)
    value = f"{name[:6].upper()}-{_random_string(min_len, max_len)}"
    return value[:max_len] if column.get("maxLength") else value


def main():
    parser = argparse.ArgumentParser(description="Generate a CSV data file for CSV-driven test cases")
    parser.add_argument("--endpoints", help="Path to swagger-spec.endpoints.json (from fetch_swagger.py)")
    parser.add_argument("--method", help="HTTP method of the target endpoint, e.g. POST")
    parser.add_argument("--path", help="Path of the target endpoint, e.g. /api/orders")
    parser.add_argument("--rows", type=int, required=True, help="Number of data rows to generate")
    parser.add_argument("--output", "-o", required=True, help="Output CSV file path")
    parser.add_argument("--columns", help="Comma-separated column names — replaces the auto-detected set entirely")
    parser.add_argument("--add", action="append", help="Add a column: 'name:type[:enumval1,enumval2,...]'. Repeatable.")
    parser.add_argument("--remove", help="Comma-separated column names to drop from the auto-detected set")
    parser.add_argument("--seed", type=int, help="Random seed for reproducible generation")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    try:
        columns = build_column_set(args)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    header = [c["name"] for c in columns]
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row_index in range(args.rows):
            writer.writerow([synthesize_value(c, row_index) for c in columns])

    print(
        f"Wrote {args.rows} rows, {len(header)} columns ({', '.join(header)}) to {args.output}",
        file=sys.stderr,
    )
    if _UNSYNTHESIZABLE_NOTES:
        print("Columns needing manual review:", file=sys.stderr)
        for note in dict.fromkeys(_UNSYNTHESIZABLE_NOTES):  # de-dup, preserve order
            print(f"  - {note}", file=sys.stderr)


if __name__ == "__main__":
    main()
