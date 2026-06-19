# Upstox × Claude

A lightweight MCP server that connects your Upstox account to Claude. Ask Claude about your portfolio in plain English — holdings, P&L, positions, funds — without copy-pasting anything.

---

## What this does

Claude has no way to talk to Upstox on its own. This server acts as the bridge. It handles the Upstox OAuth flow, stores your access token in memory, and exposes a few clean tools that Claude can call during a conversation.

Once it's running, your workflow is simple — tell Claude "login upstox", open the link, approve it, and then just ask whatever you want. "What's my portfolio looking like?" "How much cash do I have?" "Show me today's positions." It works.

---

## Tools available

| Tool | What it does |
|---|---|
| `login_upstox` | Generates the OAuth login URL. Run this once a day. |
| `get_profile` | Returns your name, email, and user ID. |
| `get_holdings` | Long-term holdings with avg price, LTP, and P&L per stock. |
| `get_positions` | Intraday/short-term positions for the current session. |
| `get_funds` | Available margin, used margin, and net balance. |
| `get_pnl_summary` | Combined P&L across holdings and today's positions. |

---

## Stack

Python, [MCP](https://github.com/anthropics/mcp), Starlette, Uvicorn. That's it. No database, no frontend, no nonsense.

---

## Setup

### 1. Upstox Developer App

Go to [upstox.com/developer](https://upstox.com/developer) and create an app. You'll get an API key and secret. Set the redirect URI to wherever you're deploying this — you can update it later.

### 2. Clone and configure

```bash
git clone https://github.com/Manu3511/UPSTOX-x-Claude.git
cd UPSTOX-x-Claude
pip install -r requirements.txt
```

Set these environment variables before running:

```
UPSTOX_API_KEY=your_key
UPSTOX_API_SECRET=your_secret
UPSTOX_REDIRECT_URI=https://your-domain.com/callback
```

### 3. Run locally

```bash
python upstox_mcp.py
```

Server starts on port 8080 by default. Override with `PORT=XXXX` if needed.

---

## Deploying on Render

This is what I use. Free tier works fine for personal use — just know that the server sleeps after inactivity, so the first request each session takes a few seconds to wake up. For a daily portfolio check, that's not a problem.

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service → connect your repo
3. Render detects Python automatically via the `Procfile`
4. Add your three environment variables in the Render dashboard under Environment
5. Update your Upstox app's redirect URI to `https://your-render-url.onrender.com/callback`
6. Deploy

Your SSE endpoint will be at `https://your-render-url.onrender.com/sse`.

---

## Connecting to Claude

Go to Claude.ai → Settings → Integrations → Add custom integration. Paste your SSE URL. Done.

After that, just start a conversation and say "login upstox". Claude will handle the rest.

---

## A note on the token

The access token lives in memory (`_access_token` global). It resets every time the server restarts — which on Render's free tier happens after idle periods. That's why the README says to login once per day. It's a deliberate tradeoff to keep things simple and stateless. If you want persistence, you'd need to write the token to a file or environment variable after auth, which is a small change to `handle_callback`.

---

## Files

```
upstox_mcp.py      — the whole server, one file
requirements.txt   — dependencies
Procfile           — tells Render how to start the server
```

---

## Disclaimer

This is a personal tool, not a financial product. It reads data from your Upstox account — it cannot place orders or move money. Use it however you like, but don't blame it for your stock picks.
