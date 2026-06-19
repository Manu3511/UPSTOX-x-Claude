import os
import asyncio
import requests
from datetime import datetime
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, HTMLResponse
from starlette.routing import Mount, Route
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
import uvicorn

API_KEY = os.getenv("UPSTOX_API_KEY", "")
API_SECRET = os.getenv("UPSTOX_API_SECRET", "")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8080/callback")
PORT = int(os.getenv("PORT", 8080))
BASE_URL = "https://api.upstox.com/v2"

_access_token = None

mcp = Server("upstox-mcp")
sse = SseServerTransport("/messages/")

TOOLS = [
    Tool(name="login_upstox",    description="Get Upstox login URL (run once per day)", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_profile",     description="Get your Upstox profile",                 inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_holdings",    description="Get holdings with P&L",                   inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_positions",   description="Get today's positions",                   inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_funds",       description="Get available funds and margin",           inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_pnl_summary", description="Get combined P&L summary",                inputSchema={"type": "object", "properties": {}}),
]

@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS

@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    global _access_token
    try:
        if name == "login_upstox":
            auth_url = (
                f"https://api.upstox.com/v2/login/authorization/dialog"
                f"?response_type=code&client_id={API_KEY}&redirect_uri={REDIRECT_URI}"
            )
            result = f"🔐 Open this URL in your browser to login to Upstox:\n\n{auth_url}\n\nAfter logging in, come back here and ask me anything about your portfolio!"
        elif not _access_token:
            result = "⚠️ Not logged in. Please call login_upstox first."
        else:
            headers = {"Authorization": f"Bearer {_access_token}", "Accept": "application/json"}

            if name == "get_profile":
                p = requests.get(f"{BASE_URL}/user/profile", headers=headers).json().get("data", {})
                result = f"👤 Name: {p.get('user_name')} | Email: {p.get('email')} | ID: {p.get('user_id')}"

            elif name == "get_holdings":
                holdings = requests.get(f"{BASE_URL}/portfolio/long-term-holdings", headers=headers).json().get("data", [])
                if not holdings:
                    result = "No holdings found."
                else:
                    lines = ["📊 **Your Holdings**\n"]
                    ti = tc = 0
                    for h in holdings:
                        qty = h.get("quantity", 0)
                        avg = h.get("average_price", 0)
                        ltp = h.get("last_price", 0)
                        inv = qty * avg; cur = qty * ltp; pnl = cur - inv
                        pct = (pnl / inv * 100) if inv else 0
                        ti += inv; tc += cur
                        e = "🟢" if pnl >= 0 else "🔴"
                        lines.append(f"{e} **{h.get('tradingsymbol')}** | Qty:{qty} | Avg:₹{avg:.2f} | LTP:₹{ltp:.2f} | P&L:₹{pnl:.2f} ({pct:.1f}%)")
                    tp = tc - ti; tpct = (tp/ti*100) if ti else 0; e = "🟢" if tp >= 0 else "🔴"
                    lines += [f"\n{e} Invested: ₹{ti:,.2f} | Current: ₹{tc:,.2f} | P&L: ₹{tp:,.2f} ({tpct:.1f}%)"]
                    result = "\n".join(lines)

            elif name == "get_positions":
                positions = requests.get(f"{BASE_URL}/portfolio/short-term-positions", headers=headers).json().get("data", [])
                if not positions:
                    result = "No open positions today."
                else:
                    lines = ["📈 **Today's Positions**\n"]
                    for p in positions:
                        pnl = p.get("unrealised_profit", 0); e = "🟢" if pnl >= 0 else "🔴"
                        lines.append(f"{e} **{p.get('tradingsymbol')}** | Qty:{p.get('quantity')} | Avg:₹{p.get('average_price',0):.2f} | LTP:₹{p.get('last_price',0):.2f} | P&L:₹{pnl:.2f}")
                    result = "\n".join(lines)

            elif name == "get_funds":
                eq = requests.get(f"{BASE_URL}/user/get-funds-and-margin?segment=SEC", headers=headers).json().get("data", {}).get("equity", {})
                result = f"💰 Available: ₹{eq.get('available_margin',0):,.2f} | Used: ₹{eq.get('used_margin',0):,.2f} | Net: ₹{eq.get('net',0):,.2f}"

            elif name == "get_pnl_summary":
                h = requests.get(f"{BASE_URL}/portfolio/long-term-holdings", headers=headers).json().get("data", [])
                p = requests.get(f"{BASE_URL}/portfolio/short-term-positions", headers=headers).json().get("data", [])
                inv = sum(x.get("quantity",0)*x.get("average_price",0) for x in h)
                cur = sum(x.get("quantity",0)*x.get("last_price",0) for x in h)
                lt = cur - inv; day = sum(x.get("unrealised_profit",0) for x in p); total = lt + day
                result = (f"📊 P&L Summary — {datetime.now().strftime('%d %b %Y %H:%M')}\n"
                         f"{'🟢' if lt>=0 else '🔴'} Holdings P&L : ₹{lt:,.2f}\n"
                         f"{'🟢' if day>=0 else '🔴'} Today P&L    : ₹{day:,.2f}\n"
                         f"{'🟢' if total>=0 else '🔴'} Total P&L    : ₹{total:,.2f}")
            else:
                result = f"Unknown tool: {name}"
    except Exception as e:
        result = f"❌ Error: {e}"
    return [TextContent(type="text", text=result)]


async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as (r, w):
        await mcp.run(r, w, mcp.create_initialization_options())
    return Response()


async def handle_callback(request: Request):
    global _access_token
    code = request.query_params.get("code")
    if code:
        r = requests.post(
            "https://api.upstox.com/v2/login/authorization/token",
            data={"code": code, "client_id": API_KEY, "client_secret": API_SECRET,
                  "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = r.json()
        _access_token = data.get("access_token")
        if _access_token:
            return HTMLResponse("<h2>✅ Login successful! Return to Claude and ask about your portfolio.</h2>")
        return HTMLResponse(f"<h2>❌ Login failed: {data}</h2>")
    return HTMLResponse("<h2>❌ No code received.</h2>")


async def handle_home(request: Request):
    return HTMLResponse("<h2>✅ Upstox MCP Server is running!</h2>")


app = Starlette(
    routes=[
        Route("/",         endpoint=handle_home),
        Route("/sse",      endpoint=handle_sse),
        Route("/callback", endpoint=handle_callback),
        Mount("/messages", app=sse.handle_post_message),
    ]
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
