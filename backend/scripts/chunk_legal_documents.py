#!/usr/bin/env python3
"""Split parsed legal Markdown into article-scale chunks with reviewed validity.

Reads the accepted ``legal-markdown-document-v1`` artifacts under an
operator-owned documents root, writes one deterministic chunk set per document
plus one run manifest under a separate output root outside ``knowledge/``, and
never makes anything answerable. ``--check-contract`` (alone) checks the
committed schema against the module's constants and exits 0.

Exit codes:

* ``0`` — every document is ``chunked`` or ``unstructured``.
* ``1`` — at least one document failed; the others were still processed.
* ``2`` — refused before writing (unsafe or missing root, unreadable or invalid
  catalog, over 1,000 manifests) or an unreadable contract.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.legal_structure_chunker import (  # noqa: E402
    check_contract,
    chunk_documents,
    contract_line,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", type=Path, default=None)
    parser.add_argument("--catalog", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--check-contract",
        action="store_true",
        help="Check the committed chunk schema against the module and exit without chunking.",
    )
    args = parser.parse_args(argv)

    if args.check_contract:
        if args.documents is not None or args.catalog is not None or args.output is not None:
            parser.error("--check-contract takes no other argument")
        problems = check_contract()
        if problems:
            for problem in problems:
                print("error: {}".format(problem), file=sys.stderr)
            return 2
        print(contract_line())
        return 0

    missing = [
        flag
        for flag, value in (
            ("--documents", args.documents),
            ("--catalog", args.catalog),
            ("--output", args.output),
        )
        if value is None
    ]
    if missing:
        parser.error("missing required arguments: " + ", ".join(missing))

    try:
        report = chunk_documents(args.documents, args.catalog, args.output)
    except Exception as error:
        # Never echo exception text or a traceback: both may contain document
        # text, local paths, or other operator data.
        print(json.dumps({"error": type(error).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
