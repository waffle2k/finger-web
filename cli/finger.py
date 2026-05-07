#!/usr/bin/env python3
"""finger-web CLI — query finger users and manage plan files.

Configuration via environment variables:
  FINGER_WEB_URL   Base URL of the finger-web instance (default: http://localhost:5000)
  FINGER_USER      Username for authenticated endpoints (upload)
  FINGER_PASS      Password for authenticated endpoints (upload)
"""

import argparse
import os
import sys

try:
    import requests
except ImportError:
    print("requests is required: pip install requests", file=sys.stderr)
    sys.exit(1)

BASE_URL = os.environ.get("FINGER_WEB_URL", "http://localhost:5000").rstrip("/")


def _get_auth():
    user = os.environ.get("FINGER_USER", "")
    passwd = os.environ.get("FINGER_PASS", "")
    return (user, passwd) if user and passwd else None


def cmd_query(args):
    target = args.username
    url = f"{BASE_URL}/api/finger/{target}" if target else f"{BASE_URL}/api/finger"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            print(data.get("result", "").rstrip())
        else:
            print(data.get("error", "Unknown error"), file=sys.stderr)
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"Cannot connect to {BASE_URL}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_plan(args):
    auth = _get_auth()
    if not auth:
        print(
            "Set FINGER_USER and FINGER_PASS environment variables to authenticate.",
            file=sys.stderr,
        )
        sys.exit(1)

    plan_file = args.file
    if not os.path.exists(plan_file):
        print(f"File not found: {plan_file}", file=sys.stderr)
        sys.exit(1)

    with open(plan_file, "rb") as f:
        try:
            resp = requests.post(
                f"{BASE_URL}/api/upload",
                files={"file": (os.path.basename(plan_file), f, "text/plain")},
                auth=auth,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            print(data.get("message", "Upload successful."))
        except requests.exceptions.ConnectionError:
            print(f"Cannot connect to {BASE_URL}", file=sys.stderr)
            sys.exit(1)
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="finger-web",
        description="Query finger users and manage plan files via finger-web.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    q = sub.add_parser("query", aliases=["q"], help="Finger a user")
    q.add_argument("username", nargs="?", default="", help="User to finger, e.g. pete@peteftw.com")

    sub.add_parser("plan", help="Upload your plan file").add_argument(
        "file", help="Path to the plan text file"
    )

    args = parser.parse_args()

    if args.command in ("query", "q"):
        cmd_query(args)
    elif args.command == "plan":
        cmd_plan(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
