#!/usr/bin/env python3
"""Publish this gallery to GitHub Pages (docs/ folder).

It reuses the GitHub credential already stored on this machine (Git Credential
Manager). Nothing is pushed unless you pass --yes.

    python tools/publish_pages.py                       # dry-run: show what would happen
    python tools/publish_pages.py --yes                  # create/update repo + enable Pages
    python tools/publish_pages.py --yes --repo derek-prompts --private

What it does
  1. reads https://github.com credential via `git credential fill`
  2. creates the public repo if missing (API)
  3. commits the whole package and pushes to main
  4. enables Pages with source = main /docs
  5. prints the final URL and waits for the first build
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"
DEFAULT_REPO = "derek-prompts"


def arg(name: str, default: str | None = None) -> str | None:
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def token() -> str:
    out = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        env={"GIT_TERMINAL_PROMPT": "0", **__import__("os").environ},
    ).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("no GitHub credential found (git credential fill returned nothing)")


def api(method: str, path: str, tok: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {tok}",
            "User-Agent": "derek-prompt-publish",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, {"message": raw.decode("utf-8", "replace")[:300]}
    except Exception as e:  # noqa: BLE001
        return 0, {"message": f"{type(e).__name__}: {e}"}


def api_retry(method: str, path: str, tok: str, body: dict | None = None, tries: int = 4) -> tuple[int, dict]:
    """This network truncates GitHub API responses now and then — retry, then trust a GET."""
    last: tuple[int, dict] = (0, {})
    for i in range(tries):
        status, data = api(method, path, tok, body)
        if status:
            return status, data
        last = (status, data)
        time.sleep(1.5 * (i + 1))
    if method != "GET":
        check, body2 = api("GET", path, tok)
        if check in (200, 201, 204):
            return check, body2
    return last


def git(*args: str) -> int:
    return subprocess.run(["git", *args], cwd=ROOT).returncode


def main() -> None:
    tok = token()
    status, me = api_retry("GET", "/user", tok)
    if status != 200:
        raise SystemExit(f"cannot authenticate with GitHub: {status} {me}")
    user = me["login"]
    repo = arg("--repo", DEFAULT_REPO)
    private = "--private" in sys.argv
    full = f"{user}/{repo}"
    url = f"https://{user}.github.io/{repo}/"

    print(f"account : {user}")
    print(f"repo    : {full}  ({'private' if private else 'PUBLIC'})")
    print(f"pages   : {url}")

    if "--yes" not in sys.argv:
        print("\n[dry-run] nothing pushed. Re-run with --yes to publish.")
        return

    # 1. repo
    status, data = api_retry("GET", f"/repos/{full}", tok)
    if status == 404:
        status, data = api_retry(
            "POST",
            "/user/repos",
            tok,
            {"name": repo, "private": private, "description": "德里克文 · 提示词库 — X 原创 AI 提示词归档（42 条）", "auto_init": False},
        )
        print(f"created repo: {status}")
        if status not in (200, 201):
            raise SystemExit(f"cannot create repo: {data}")
    else:
        print("repo already exists — updating")

    # 2. commit + push
    if not (ROOT / ".git").exists():
        git("init", "-b", "main")
    git("add", "-A")
    git("-c", "user.name=Derek Wen", "-c", "user.email=derek@localhost", "commit", "-m", "德里克文 · 提示词库：42 条 X 原创 AI 提示词（配图本地化 webp）")
    git("remote", "remove", "origin")
    git("remote", "add", "origin", f"https://x-access-token:{tok}@github.com/{full}.git")
    if git("push", "-u", "origin", "main", "-f") != 0:
        raise SystemExit("git push failed")
    print("pushed → main")

    # 3. pages
    status, data = api_retry("GET", f"/repos/{full}/pages", tok)
    body = {"source": {"branch": "main", "path": "/docs"}}
    if status == 404:
        status, data = api_retry("POST", f"/repos/{full}/pages", tok, body)
        print(f"pages enabled: {status} {data.get('html_url') if status < 300 else data}")
    elif status == 200:
        api_retry("PUT", f"/repos/{full}/pages", tok, body)
        print("pages updated → main /docs")

    # 4. wait for build
    for _ in range(30):
        time.sleep(10)
        status, data = api_retry("GET", f"/repos/{full}/pages/builds/latest", tok)
        state = data.get("status")
        print(f"  build: {state}")
        if state == "built":
            break
    print(f"\n✅ {url}")


if __name__ == "__main__":
    main()
