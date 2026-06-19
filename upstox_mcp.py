"""
Upstox MCP Server - Railway Deployment
Uses HTTP + SSE transport so Claude.ai can connect via https URL.
"""

import json
import os
import threading
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
import uvicorn
import anyio

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
API_KEY      = os.getenv("UPSTOX_API_KEY")
API_SECRET   = os.getenv("UPSTOX_API_SECRET")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8000/callback")
PORT         = int(os.getenv("PORT", 8080))
BASE_URL     = "https://api.upstox.com/v2"

_access_token: str | None = None

# ── OAuth Login ───────────────────────────────────────────────────────────────

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _access_token
        query = parse_qs(urlparse(self.path).query)
        code  = query.get("code", [None])[0]
        if code:
            r = requests.post(
                "https://api.upstox.com/v2/login/authorization/token",
                data={
                    "code":          code,
                    "client_id":     API_KEY,
                    "client_secret": API_SECRET,
                    "redirect_uri":  REDIRECT_URI,
                    "grant_type":    "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            _access_token = r.json().get("access_token")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Login successful! Return to Claude.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>Login failed. Try again.</h2>")

    def log_message(self, *args):
        pass


def _start_callback_server():
    port = int(REDIRECT_URI.split(":")[-1].split("/")[0])
    HTTPServer(("0.0.0.0", port), CallbackHandler).handle_request()


def login_upstox() -> str:
    auth_url = (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code&client_id={API_KEY}&redirect_uri={REDIRECT_URI}"
    )
    t = threading.Thread(target=_start_callback_server, daemon=True)
    t.start()
    return f"🔐 Open this URL in your browser to login:\n\n{auth_url}\n\nAfter login, come back here."


# ── API Helpers ───────────────────────────────────────────────────────────────

def _headers():
    if not _access_token:
        raise RuntimeError("Not logged in. Please call login_upstox first.")
    return {"Authorization": f"Bearer {_access_token}", "Accept": "application/json"}


def _get(endpoint: str) -> dict:
    r = requests.get(f"{BASE_URL}{endpoint}", headers=_headers())
    r.raise_for_status()
    return r.json()


# ── Tools ─────────────────────────────────────────────────────────────────────

def get_holdings() -> str:
    data     = _get("/portfolio/long-term-holdings")
    holdings = data.get("data", [])
    if not holdings:
        return "No holdings found."

    lines = ["📊 **Your Holdings**\n"]
    total_invested = total_current = 0

    for h in holdings:
        symbol    = h.get("tradingsymbol", "N/A")
        qty       = h.get("quantity", 0)
        avg       = h.get("average_price", 0)
        ltp       = h.get("last_price", 0)
        invested  = qty * avg
        current   = qty * ltp
        pnl       = current - invested
        pnl_pct   = (pnl / invested * 100) if invested else 0
        emoji     = "🟢" if pnl >= 0 else "🔴"
        total_invested += invested
        total_current  += current
        lines.append(
            f"{emoji} **{symbol}** | Qty: {qty} | Avg: ₹{avg:.2f} | "
            f"LTP: ₹{ltp:.2f} | P&L: ₹{pnl:.2f} ({pnl_pct:.2f}%)"
        )

    total_pnl     = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0
    e = "🟢" if total_pnl >= 0 else "🔴"
    lines += [
        f"\n{e} **Total Invested :** ₹{total_invested:,.2f}",
        f"{e} **Current Value  :** ₹{total_current:,.2f}",
        f"{e} **Overall P&L    :** ₹{total_pnl:,.2f} ({total_pnl_pct:.2f}%)",
    ]
    return "\n".join(lines)


def get_positions() -> str:
    data      = _get("/portfolio/short-term-positions")
    positions = data.get("data", [])
    if not positions:
        return "No open positions today."

    lines = ["📈 **Today's Positions**\n"]
    for p in positions:
        symbol = p.get("tradingsymbol", "N/A")
        qty    = p.get("quantity", 0)
        avg    = p.get("average_price", 0)
        ltp    = p.get("last_price", 0)
        pnl    = p.get("unrealised_profit", 0)
        prod   = p.get("product", "")
        emoji  = "🟢" if pnl >= 0 else "🔴"
        lines.append(
            f"{emoji} **{symbol}** [{prod}] | Qty: {qty} | Avg: ₹{avg:.2f} | "
            f"LTP: ₹{ltp:.2f} | Unrealised P&L: ₹{pnl:.2f}"
        )
    return "\n".join(lines)


def get_funds() -> str:
    data   = _get("/user/get-funds-and-margin?segment=SEC")
    equity = data.get("data", {}).get("equity", {})
    return (
        f"💰 **Funds & Margin**\n\n"
        f"Available Margin : ₹{equity.get('available_margin', 0):,.2f}\n"
        f"Used Margin      : ₹{equity.get('used_margin', 0):,.2f}\n"
        f"Net Balance      : ₹{equity.get('net', 0):,.2f}"
    )


def get_profile() -> str:
    p = _get("/user/profile").get("data", {})
    return (
        f"👤 **Profile**\n\n"
        f"Name    : {p.get('user_name', 'N/A')}\n"
        f"Email   : {p.get('email', 'N/A')}\n"
        f"User ID : {p.get('user_id', 'N/A')}\n"
        f"Broker  : {p.get('broker', 'Upstox')}"
    )


def get_pnl_summary() -> str:
    holdings  = _get("/portfolio/long-term-holdings").get("data", [])
    positions = _get("/portfolio/short-term-positions").get("data", [])

    invested  = sum(h.get("quantity", 0) * h.get("average_price", 0) for h in holdings)
    current   = sum(h.get("quantity", 0) * h.get("last_price", 0)    for h in holdings)
    lt_pnl    = current - invested
    day_pnl   = sum(p.get("unrealised_profit", 0) for p in positions)
    total     = lt_pnl + day_pnl

    e1 = "🟢" if lt_pnl  >= 0 else "🔴"
    e2 = "🟢" if day_pnl >= 0 else "🔴"
    e3 = "🟢" if total   >= 0 else "🔴"

    return (
        f"📊 **P&L Summary** — {datetime.now().strftime('%d %b %Y %H:%M')}\n\n"
        f"{e1} Long-Term Holdings P&L : ₹{lt_pnl:,.2f}\n"
        f"{e2} Today's Positions P&L  : ₹{day_pnl:,.2f}\n"
        f"{e3} **Total P&L**          : ₹{total:,.2f}"
    )


# ── MCP Server ────────────────────────────────────────────────────────────────

from mcp.types import Tool, TextContent

mcp = Server("upstox-mcp")

TOOLS = [
    Tool(name="login_upstox",    description="Get login URL for Upstox (run once per day)",         inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_profile",     description="Get your Upstox profile",                             inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_holdings",    description="Get long-term holdings with P&L",                     inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_positions",   description="Get today's intraday/short-term positions",           inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_funds",       description="Get available funds and margin",                      inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_pnl_summary", description="Get combined P&L summary for holdings + today",      inputSchema={"type": "object", "properties": {}}),
]

TOOL_MAP = {
    "login_upstox":    login_upstox,
    "get_profile":     get_profile,
    "get_holdings":    get_holdings,
    "get_positions":   get_positions,
    "get_funds":       get_funds,
    "get_pnl_summary": get_pnl_summary,
}

@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS

@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        fn     = TOOL_MAP.get(name)
        result = fn() if fn else f"Unknown tool: {name}"
    except RuntimeError as e:
        result = f"⚠️ {e}"
    except Exception as e:
        result = f"❌ Error: {e}"
    return [TextContent(type="text", text=result)]


# ── Starlette App (SSE) ───────────────────────────────────────────────────────

sse = SseServerTransport("/messages/")

async def handle_sse(request: Request) -> Response:
    async with sse.connect_sse(request.scope, request.receive, request._send) as (r, w):
        await mcp.run(r, w, mcp.create_initialization_options())
    return Response()

async def handle_callback(request: Request) -> Response:
    global _access_token
    code = request.query_params.get("code")
    if code:
        r = requests.post(
            "https://api.upstox.com/v2/login/authorization/token",
            data={
                "code":          code,
                "client_id":     API_KEY,
                "client_secret": API_SECRET,
                "redirect_uri":  REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        _access_token = r.json().get("access_token")
        return Response("<h2>✅ Login successful! Return to Claude.</h2>", media_type="text/html")
    return Response("<h2>❌ Login failed.</h2>", media_type="text/html")


app = Starlette(
    routes=[
        Route("/sse",      endpoint=handle_sse),
        Route("/callback", endpoint=handle_callback),
        Mount("/messages", app=sse.handle_post_message),
    ]
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
