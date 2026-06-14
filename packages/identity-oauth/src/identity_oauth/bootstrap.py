"""Twitch OAuth 首次授權（Authorization Code Flow + 本地 callback）。"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import load_dotenv

from identity_oauth.env_file import env_updates_for_authorization, update_env_values
from identity_oauth.protocol import AccountRole
from identity_oauth.scopes import scopes_for_role
from identity_oauth.single_account import read_single_account_mode

AUTHORIZE_URL = "https://id.twitch.tv/oauth2/authorize"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
DEFAULT_REDIRECT_URI = "http://localhost:17563"
DEFAULT_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class AuthorizationResult:
    role: AccountRole
    refresh_token: str
    access_token: str
    user_id: str
    login: str
    scopes: list[str]


@dataclass
class _CallbackState:
    done: threading.Event
    code: str = ""
    error: str = ""
    error_description: str = ""


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    scopes: list[str],
    force_verify: bool = True,
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
    }
    if force_verify:
        params["force_verify"] = "true"
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        return response.json()


async def fetch_token_info(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            VALIDATE_URL,
            headers={"Authorization": f"OAuth {access_token}"},
        )
        response.raise_for_status()
        return response.json()


def _build_callback_handler(state: _CallbackState, expected_path: str) -> type[BaseHTTPRequestHandler]:
    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != expected_path:
                self.send_response(404)
                self.end_headers()
                return

            query = parse_qs(parsed.query)
            code = query.get("code", [""])[0].strip()
            if code:
                state.code = code
                state.done.set()
                self._write_page(status=200, title="授權成功", body="已完成授權，請返回終端機。")
                return

            state.error = query.get("error", ["授權失敗"])[0].strip() or "授權失敗"
            state.error_description = query.get("error_description", [""])[0].strip()
            state.done.set()
            detail = state.error_description or "請重新嘗試授權。"
            self._write_page(status=400, title="授權失敗", body=detail)

        def _write_page(self, *, status: int, title: str, body: str) -> None:
            html = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                f"<title>{title}</title></head><body>"
                f"<h2>{title}</h2><p>{body}</p>"
                "<p>你可以關閉這個視窗。</p>"
                "</body></html>"
            )
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

    return OAuthCallbackHandler


def _wait_for_callback(
    state: _CallbackState,
    *,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not state.done.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("授權逾時，請重新執行")
        state.done.wait(timeout=min(1.0, remaining))

    if state.error:
        detail = state.error_description
        raise RuntimeError(f"{state.error}: {detail}" if detail else state.error)
    if not state.code:
        raise RuntimeError("未取得授權碼")


async def authorize_role(
    role: AccountRole,
    *,
    environ: dict[str, str] | None = None,
    env_path: Path | None = None,
    open_browser: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> AuthorizationResult:
    env = environ if environ is not None else os.environ
    client_id = (env.get("TWITCH_CLIENT_ID") or "").strip()
    client_secret = (env.get("TWITCH_CLIENT_SECRET") or "").strip()
    redirect_uri = (env.get("TWITCH_REDIRECT_URI") or DEFAULT_REDIRECT_URI).strip()
    if not client_id or not client_secret:
        raise RuntimeError("請先在 .env 設定 TWITCH_CLIENT_ID 與 TWITCH_CLIENT_SECRET")

    single_account = read_single_account_mode(env)
    scopes = scopes_for_role(role, single_account=single_account)
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"

    callback_state = _CallbackState(done=threading.Event())
    handler = _build_callback_handler(callback_state, path)
    server = HTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    auth_url = build_authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scopes=scopes,
    )

    print(f"\n角色：{role}")
    print(f"本地 callback：{redirect_uri}")
    print(f"授權網址：\n{auth_url}\n")

    if open_browser:
        try:
            webbrowser.open(auth_url)
            print("已嘗試開啟瀏覽器。")
        except Exception as exc:
            print(f"無法自動開啟瀏覽器：{exc}", file=sys.stderr)

    try:
        print("等待授權…（請在瀏覽器完成 Twitch 登入）")
        _wait_for_callback(callback_state, timeout_seconds=timeout_seconds)

        token_payload = await exchange_code_for_token(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            code=callback_state.code,
        )
        access_token = str(token_payload.get("access_token", "")).strip()
        refresh_token = str(token_payload.get("refresh_token", "")).strip()
        if not access_token or not refresh_token:
            raise RuntimeError("Twitch token 回應缺少 access_token 或 refresh_token")

        token_info = await fetch_token_info(access_token)
        user_id = str(token_info.get("user_id", "")).strip()
        login = str(token_info.get("login", "")).strip()
        raw_scopes = token_info.get("scopes", [])
        scope_list = [str(item) for item in raw_scopes] if isinstance(raw_scopes, list) else []

        target_env = env_path or Path(env.get("ENV_FILE", ".env"))
        if not target_env.is_absolute():
            target_env = Path.cwd() / target_env
        updates = env_updates_for_authorization(
            role,
            refresh_token=refresh_token,
            user_id=user_id,
            single_account=single_account,
        )
        update_env_values(updates, env_path=target_env)

        return AuthorizationResult(
            role=role,
            refresh_token=refresh_token,
            access_token=access_token,
            user_id=user_id,
            login=login,
            scopes=scope_list,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def _print_authorization_result(result: AuthorizationResult, *, env_path: Path) -> None:
    print("\n授權完成")
    print(f"  role={result.role}")
    print(f"  login={result.login}")
    print(f"  user_id={result.user_id}")
    print(f"  access_token_prefix={result.access_token[:8]}...")
    print(f"  refresh_token_prefix={result.refresh_token[:8]}...")
    print(f"  scopes={', '.join(result.scopes) if result.scopes else '(validate 未回傳)'}")
    print(f"  已寫入 {env_path}")
    if result.role == "channel" and not read_single_account_mode():
        print("\n下一步：若使用雙帳號，請再執行 Bot 帳號授權：")
        print("  uv run python scripts/first_time_auth.py --role bot")


async def _authorize_async(args: argparse.Namespace) -> int:
    load_dotenv(args.env_file)
    env_path = Path(args.env_file) if args.env_file else Path(".env")
    try:
        result = await authorize_role(
            args.role,
            env_path=env_path,
            open_browser=not args.no_browser,
            timeout_seconds=args.timeout,
        )
    except (RuntimeError, TimeoutError, httpx.HTTPError) as exc:
        print(f"\n授權失敗：{exc}", file=sys.stderr)
        return 1

    _print_authorization_result(result, env_path=env_path)
    return 0


def build_authorize_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Twitch OAuth 首次授權（streamer-toolbox 內建）")
    parser.add_argument(
        "--role",
        choices=["channel", "bot"],
        default="channel",
        help="授權帳號角色（預設 channel＝主帳號）",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="要寫入的 .env 路徑（預設 .env）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"等待瀏覽器 callback 秒數（預設 {DEFAULT_TIMEOUT_SECONDS}）",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="不要自動開啟瀏覽器（手動複製授權網址）",
    )
    return parser


def run_authorize_cli(argv: list[str] | None = None) -> int:
    parser = build_authorize_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_authorize_async(args))


if __name__ == "__main__":
    raise SystemExit(run_authorize_cli())
