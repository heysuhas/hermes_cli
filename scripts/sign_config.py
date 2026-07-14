#!/usr/bin/env python3
"""Enterprise tool to sign Hermes managed configuration files.

Computes HMAC-SHA256 of the configuration file and writes it to a signature file.
"""

import argparse
import hashlib
import hmac
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Sign Hermes configuration files.")
    parser.add_argument("file", help="Path to config.yaml or .env file to sign")
    parser.add_argument(
        "--secret",
        default=None,
        help="Signing secret key. If not provided, reads HERMES_ENTERPRISE_SECRET env var.",
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.is_file():
        print(f"Error: {file_path} is not a valid file.", file=sys.stderr)
        sys.exit(1)

    secret = args.secret or os.environ.get("HERMES_ENTERPRISE_SECRET")
    if not secret:
        print("Warning: Neither --secret nor HERMES_ENTERPRISE_SECRET env var is set.", file=sys.stderr)
        print("Using fallback default key: 'EnterpriseSecretKey2026'", file=sys.stderr)
        secret = "EnterpriseSecretKey2026"

    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except Exception as exc:
        print(f"Error reading file {file_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    signature = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()

    sig_path = file_path.with_name(f"{file_path.name}.sig")
    try:
        with open(sig_path, "w", encoding="utf-8") as f:
            f.write(signature + "\n")
        print(f"Successfully signed {file_path.name}.")
        print(f"Signature written to: {sig_path}")
        print(f"HMAC-SHA256: {signature}")
    except Exception as exc:
        print(f"Error writing signature file {sig_path}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
