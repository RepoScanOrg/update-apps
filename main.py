#!/usr/bin/env python3
import argparse
import datetime as dt
import glob
from hashlib import file_digest
import os
import sys
import time
import subprocess
from typing import Optional

# pip install veracode-api-py
from veracode_api_py import VeracodeAPI

def log(msg: str) -> None:
    """
    Simple logger with timestamp.
    """
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


def create_profile(api: VeracodeAPI, name: str, policy: Optional[str], business_crit: Optional[str], tags: Optional[str], dry_run: bool) -> str:
    """
    Create an application profile with 'name'. Returns the application GUID/ID (string).
    """
    # get_app_by_name returns a dict or None depending on library version
    existing = api.get_app_by_name(name)
    # TODO: validate this actually returns none if app doesn't exist, and not just empty dict.
    if len(existing) > 0:
        try:
            app_id = existing[0]["guid"]
        except KeyError:
            app_id = existing[0]["id"]
        log(f"   App exists: {name} (id={app_id})")
        return str(app_id)

    log(f"   Creating app: {name}")
    if dry_run:
        return "DRY_RUN_APP_ID"

    # Create app: method signature may vary slightly by version, but commonly:
    # create_app(name, policy=None, business_criticality=None, teams=None, business_unit=None, description=None, tags=None)
    created = api.create_app(
        name,
        business_criticality=business_crit if business_crit else 'VERY_HIGH',
        policy_guid=policy if policy else None,
        tags=tags if tags else None,
    )
    app_id = created.get("guid") or created.get("id") or created.get("app_id")
    if not app_id:
        raise RuntimeError(f"Unable to determine created app id for {name}. Response: {created}")
    log(f"   App created: {name} (id={app_id})")
    return str(app_id)

def wrapper_upload_scan(app_name, file_path):

    log(f">> Starting scan for {app_name}")
    # Use the user to run the pipeline scan on app
    command = ["java", "-jar", "resources/VeracodeJavaAPI.jar", "-action", "UploadAndScan", "-appname", app_name, "-createprofile", "false", "-filepath",file_path, "-version", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")]

    subprocess.call(command)

def upload_artifact(api: VeracodeAPI, app_id: str, filepath: str, dry_run: bool):
    # Common signature: upload_file(app_id, filepath)
    resp = api.upload_file(app_id=app_id, file=filepath)
    return resp




def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Batch create Veracode App Profiles and upload artifacts using veracode-api-py."
    )
    p.add_argument("--src-dir", required=True, help="Folder containing items to upload.")
    p.add_argument(
        "--glob",
        action="append",
        default=None,
        help=(
            "Glob pattern(s) within src-dir. Repeat --glob to specify multiple, or pass a comma-separated list. "
            "Default: *.zip"
        ),
    )
    p.add_argument("--prefix", default="MyOrg-", help="App name prefix (default: MyOrg-).")
    p.add_argument("--policy", default="", help="Policy name (optional).")
    p.add_argument("--business-criticality", default="", choices=["Very High", "High", "Medium", "Low", ""],
                   help='Business criticality, or leave empty to skip. Options: "Very High", "High", "Medium", "Low".')
    p.add_argument("--tags", default="", help="Comma-separated tags (optional).")
    p.add_argument("--start-prescan", action="store_true", help="Start a prescan after upload.")
    p.add_argument("--start-scan", action="store_true", help="Start a scan after prescan.")
    p.add_argument("--sleep-after-prescan", type=int, default=0,
                   help="Optional seconds to sleep after prescan before starting scan (default: 0).")
    p.add_argument("--dry-run", action="store_true", help="Print actions without making changes.")
    return p.parse_args()



# Takes in args.src_dir and args.glob, and processes each file in the directory matching the glob pattern.
def main():
    args = parse_args()

    src_dir = os.path.abspath(args.src_dir)
    if not os.path.isdir(src_dir):
        print(f"Source directory not found: {src_dir}", file=sys.stderr)
        sys.exit(1)
    # Normalize multiple glob patterns: allow repeated --glob flags or comma-separated lists
    patterns = []
    if args.glob is None:
        patterns = ["*.zip", "*.jar", "*.js", "*.dll", "*.tar", "*.tar.gz", "*.war"]
    else: # I HAVE NO IDEA IF THIS WORKS
        for g in args.glob:
            patterns.extend([s.strip() for s in g.split(",") if s.strip()])

    # Collect unique files matching any of the patterns
    items_set = set()
    for patt in patterns:
        search_pattern = os.path.join(src_dir, patt)
        for match in glob.glob(search_pattern):
            if os.path.isfile(match):
                items_set.add(os.path.abspath(match))
    items = sorted(items_set)
    if not items:
        print(f"No items matched patterns {patterns} in: {src_dir}", file=sys.stderr)
        sys.exit(1)

    log(f"Found {len(items)} item(s) in {src_dir} with patterns {patterns}")

    # Initialize API clients
    api = VeracodeAPI()

    for item in items:
        # Items is a bunch of abs paths, need to make relative.
        base = os.path.basename(item)
        safe_base = "_".join(base.split())  # normalize spaces to underscores
        app_name = f"{args.prefix}{safe_base}"

        log("=" * 50)
        log(f"Processing: {item}")
        log(f"App name: {app_name}")

        app_id = create_profile(
            api=api,
            name=app_name,
            policy=args.policy.strip() or None,
            business_crit=args.business_criticality.strip() or None,
            tags=args.tags.strip() or None,
            dry_run=args.dry_run,
        )
        result = wrapper_upload_scan(app_name, item)

        log(f"Done: {item}")

    log("All done.")


if __name__ == "__main__":
    main()