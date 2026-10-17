#!/usr/bin/env python3
"""Prove, before a push, that every reusable workflow gets the permissions it asks for.

Why: release.yml calls ci.yml, whose weekly-alert job asks for `issues: write`. A called workflow can never have more
permission than the job that calls it, and release.yml only gave `contents: write`. GitHub does not skip the job in that
case. It refuses to start the whole run ("startup_failure", no jobs, no log), so the v0.5.5 release page stayed empty.
actionlint does not know this rule. This reads every workflow in .github/workflows and names the caller, the called file,
the job and the permission that is missing.

usage: scripts/check-workflow-permissions.py   (needs PyYAML: pip install pyyaml)
"""
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("This check needs PyYAML: pip install pyyaml")

ROOT = Path(__file__).resolve().parents[1]
FLOWS = ROOT / ".github" / "workflows"
LEVEL = {"none": 0, "read": 1, "write": 2}


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def scopes(value) -> dict[str, int] | None:
    """A permissions block as scope -> level, or None when nothing is set."""
    if value is None:
        return None
    if value == "write-all":
        return {"*": 2}
    if value == "read-all":
        return {"*": 1}
    return {name: LEVEL[str(level)] for name, level in (value or {}).items()}


def grant(held: dict[str, int] | None, scope: str) -> int:
    if held is None:
        return 1  # nothing set: the repository default, which is at best read for the checks that matter here
    return held.get(scope, held.get("*", 0))


def problems(caller: Path, flow: dict, seen: tuple = ()) -> list[str]:
    found = []
    for job_name, job in (flow.get("jobs") or {}).items():
        target = job.get("uses", "")
        if not target.startswith("./"):
            continue
        callee_path = ROOT / target[2:]
        if callee_path in seen:
            continue
        held = scopes(job["permissions"]) if "permissions" in job else scopes(flow.get("permissions"))
        callee = load(callee_path)
        for inner_name, inner in (callee.get("jobs") or {}).items():
            asked = scopes(inner["permissions"]) if "permissions" in inner else scopes(callee.get("permissions"))
            for scope, level in (asked or {}).items():
                if level > grant(held, scope):
                    found.append(
                        f"{caller.name}: job '{job_name}' calls {callee_path.name}, whose job '{inner_name}' asks for "
                        f"{scope}: {'write' if level == 2 else 'read'}. Give job '{job_name}' that permission, "
                        f"or GitHub refuses to start the whole run."
                    )
        found += problems(callee_path, callee, seen + (callee_path,))
    return found


def main() -> int:
    found = []
    for path in sorted(FLOWS.glob("*.y*ml")):
        found += problems(path, load(path), (path,))
    for line in found:
        print(f"error: {line}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
