"""Generate ignored build-only VB credentials from environment variables.

Values are never accepted on the command line or printed. This protects public
source and logs; it does not make credentials embedded in an executable secret.
"""

import argparse
import os
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
GENERATED = Path("Plain Craft Launcher 2/obj/PrivateBuildCredentials.g.vb")
CLIENT_ID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def read_credentials(environ):
    client_id = environ.get("PCL_MS_CLIENT_ID", "")
    api_key = environ.get("PCL_CF_API_KEY", "")
    if not CLIENT_ID_PATTERN.fullmatch(client_id):
        raise ValueError("PCL_MS_CLIENT_ID must be a UUID.")
    # CurseForge keys are opaque. Reject blanks, whitespace and control
    # characters without assuming a particular prefix or interpreting dollars.
    if not 20 <= len(api_key) <= 512 or any(
        ord(char) < 33 or ord(char) > 126 for char in api_key
    ):
        raise ValueError("PCL_CF_API_KEY must be a nonempty printable API key.")
    return client_id, api_key


def vb_string(value):
    return '"' + value.replace('"', '""') + '"'


def generate(root=ROOT, environ=None):
    destination = root / GENERATED
    # Never leave a previous build's credentials active after validation fails.
    destination.unlink(missing_ok=True)
    client_id, api_key = read_credentials(
        os.environ if environ is None else environ
    )
    source = (
        "' Generated for this build only. Never commit or upload this file.\n"
        "Friend Module BuildCredentials\n"
        f"    Friend Const MicrosoftClientId As String = {vb_string(client_id)}\n"
        f"    Friend Const CurseForgeApiKey As String = {vb_string(api_key)}\n"
        "End Module\n"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.write_text(source, encoding="utf-8", newline="\n")
    except OSError:
        destination.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    try:
        if args.clean:
            (ROOT / GENERATED).unlink(missing_ok=True)
        else:
            generate()
    except (ValueError, OSError):
        # Do not expose environment values, source lines or exception payloads.
        print("Build credential preparation failed; check the required secrets.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
