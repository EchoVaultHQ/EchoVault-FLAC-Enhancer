"""Stub replacement for inference.py used in unit tests: no onnxruntime/model needed.
Reads the real CLI contract's args and prints/exits according to --simulate."""

import argparse
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--model", type=Path)
parser.add_argument("--config", type=Path)
parser.add_argument("--input", type=Path)
parser.add_argument("--output", type=Path)
parser.add_argument("--provider", default="auto")
parser.add_argument("--self-test", action="store_true")
parser.add_argument(
    "--simulate",
    default="success",
    choices=[
        "success",
        "MODEL_NOT_FOUND",
        "INPUT_READ_FAILED",
        "ORT_INIT_FAILED",
        "GENERIC",
    ],
)
args = parser.parse_args()

EXIT_CODES = {
    "GENERIC": 1,
    "INPUT_READ_FAILED": 2,
    "MODEL_NOT_FOUND": 3,
    "ORT_INIT_FAILED": 4,
}

if args.simulate != "success":
    print(f"ERROR {args.simulate} simulated failure", file=sys.stderr)
    sys.exit(EXIT_CODES[args.simulate])

print("PROGRESS 50", flush=True)
print("PROGRESS 100", flush=True)
if args.output:
    args.output.write_bytes(b"fake-flac-bytes")
    print(f"DONE {args.output}", flush=True)
sys.exit(0)
