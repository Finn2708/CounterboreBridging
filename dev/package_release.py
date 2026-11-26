"""Build the Fusion add-in ZIP from a local release tag."""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "CounterboreBridging"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="stable release tag, for example v2.0.0")
    args = parser.parse_args()
    match = re.fullmatch(r"v?([0-9]+(?:\.[0-9]+){1,3})", args.tag)
    if not match:
        parser.error("use a stable numeric release tag, for example v2.0.0")

    ref = f"refs/tags/{args.tag}"
    manifest = f"{NAME}.manifest"
    result = subprocess.run(["git", "show", f"{ref}:{manifest}"], cwd=ROOT,
                            stdout=subprocess.PIPE, check=True)
    if json.loads(result.stdout)["version"] != match[1]:
        parser.error(f"{manifest} at {args.tag} must declare version {match[1]}")

    output = ROOT / "dist" / f"{NAME}-{args.tag}.zip"
    output.parent.mkdir(exist_ok=True)
    subprocess.run(["git", "archive", "--format=zip", f"--prefix={NAME}/",
                    f"--output={output}", ref, "--", manifest, f"{NAME}.py",
                    "config.py", "commands", "lib"], cwd=ROOT, check=True)
    print(output)


if __name__ == "__main__":
    main()
