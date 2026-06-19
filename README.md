# Upstox MCP Server — Railway Deployment Guide

## Step 1: Push to GitHub
1. Create a new repo on github.com (e.g. `upstox-mcp`)
2. Upload these 3 files: `upstox_mcp.py`, `requirements.txt`, `Procfile`

## Step 2: Deploy on Railway
1. Go to https://railway.app and sign up (free)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `upstox-mcp` repo
4. Railway auto-detects Python and deploys ✅

## Step 3: Add Environment Variables in Railway
In your Railway project → Settings → Variables, add:
```
UPSTOX_API_KEY=your_api_key_here
UPSTOX_API_SECRET=your_api_secret_here
UPSTOX_REDIRECT_URI=https://YOUR-RAILWAY-URL.railway.app/callback
```
⚠️ Replace YOUR-RAILWAY-URL with your actual Railway domain.

## Step 4: Update Upstox App Redirect URL
1. Go to https://upstox.com/developer
2. Edit your app
3. Change redirect URL to: https://YOUR-RAILWAY-URL.railway.app/callback

## Step 5: Connect to Claude.ai
1. Go to Claude.ai → Settings → Integrations
2. Add custom integration
3. URL: https://YOUR-RAILWAY-URL.railway.app/sse
4. Done! ✅

## Daily Usage
Each morning, tell Claude: "login upstox"
Claude will give you a login URL → open it → login → done!

Then ask:
- "Show my holdings"
- "What's my P&L today?"
- "How much funds do I have?"
- "Analyse my portfolio"
