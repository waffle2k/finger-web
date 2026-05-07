#!/usr/bin/env python3
"""MCP server for finger-web.

Exposes finger query and plan-upload operations as Claude tools.

Environment variables:
  FINGER_WEB_URL   Base URL of the finger-web instance (default: http://localhost:5000)
  FINGER_USER      Username for authenticated endpoints
  FINGER_PASS      Password for authenticated endpoints
"""

import os

import requests
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("FINGER_WEB_URL", "http://localhost:5000").rstrip("/")

mcp = FastMCP("finger")


def _auth():
    user = os.environ.get("FINGER_USER", "")
    passwd = os.environ.get("FINGER_PASS", "")
    return (user, passwd) if user and passwd else None


@mcp.tool()
def finger_user(username: str = "") -> str:
    """Query finger information for a user via finger-web.

    Pass a bare username (e.g. 'pete') or a user@host address
    (e.g. 'pete@peteftw.com').  Leave username empty to list currently
    logged-in users.
    """
    if username and not all(c.isalnum() or c in ".-_@" for c in username):
        return f"Invalid username: {username!r}"

    url = f"{BASE_URL}/api/finger/{username}" if username else f"{BASE_URL}/api/finger"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            return data.get("result", "No information available.").strip()
        return data.get("error", "Unknown error.")
    except requests.exceptions.ConnectionError:
        return f"Cannot connect to {BASE_URL}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def upload_plan(filename: str, content: str) -> str:
    """Upload or update a finger plan file via finger-web.

    filename  The plan filename (typically your username, e.g. 'pete').
    content   Plain-text content to publish as your .plan.

    Requires FINGER_USER and FINGER_PASS environment variables to be set.
    """
    auth = _auth()
    if not auth:
        return "Set FINGER_USER and FINGER_PASS environment variables to authenticate."

    try:
        resp = requests.post(
            f"{BASE_URL}/api/upload",
            files={"file": (filename, content.encode(), "text/plain")},
            auth=auth,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", "Upload successful.")
    except requests.exceptions.ConnectionError:
        return f"Cannot connect to {BASE_URL}"
    except requests.exceptions.HTTPError as e:
        return f"HTTP error: {e}"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
