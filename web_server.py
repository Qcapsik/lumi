# Lumi — Discord-бот (PyQZone)
# Copyright (C) 2026 Qcaps & lev4ak. Все права защищены.
"""Веб-панель управления ботом: вход через Discord OAuth2, оплата Stripe, ключи."""

import os
import secrets
import time
from pathlib import Path

import httpx
import stripe
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import database as db

load_dotenv(Path(__file__).parent / ".env")

BASE_DIR = Path(__file__).parent
SITE_DIR = BASE_DIR / "site"
PORT = int(os.getenv("PORT", os.getenv("PANEL_PORT", "8080")))

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("PANEL_REDIRECT_URI", f"http://localhost:{PORT}/auth/callback")
BOT_TOKEN = os.getenv("DISCORD_TOKEN", "")

STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
DOMAIN = os.getenv("SITE_DOMAIN", f"http://localhost:{PORT}")

stripe.api_key = STRIPE_SECRET

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API = "https://discord.com/api"

ADMIN_PERM = 0x8  # ADMINISTRATOR

app = FastAPI(title="Lumi Panel", docs_url=None, redoc_url=None)

# Тарифы: месяцы -> цена $
PLANS = {1: 7.99, 3: 14.99}

# Сессии: token -> {user_id, username, avatar, expires}
SESSIONS: dict = {}
SESSION_TTL = 24 * 3600

db.init_db()
db.create_promo("LumiAI", 10, 100000)  # Промокод LumiAI: −10%


def _new_session(user: dict, access_token: str) -> str:
    token = secrets.token_hex(24)
    SESSIONS[token] = {
        "user_id": user["id"],
        "username": user["username"],
        "avatar": user.get("avatar"),
        "access_token": access_token,
        "expires": time.time() + SESSION_TTL,
    }
    return token


def _cookie_token(request: Request) -> str | None:
    return request.cookies.get("lumi_token")


def _require_session(request: Request) -> dict:
    token = _cookie_token(request)
    s = SESSIONS.get(token or "")
    if not s or s["expires"] < time.time():
        raise HTTPException(status_code=401, detail="Не авторизован")
    return s


async def _discord_get(url: str, token: str) -> dict | list | None:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 200:
            return r.json()
        return None


async def _bot_get(url: str) -> dict | list | None:
    if not BOT_TOKEN:
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{DISCORD_API}{url}", headers={"Authorization": f"Bot {BOT_TOKEN}"})
        if r.status_code == 200:
            return r.json()
        return None


@app.get("/")
async def index():
    return FileResponse(SITE_DIR / "index.html")


@app.get("/premium.html")
async def premium():
    return FileResponse(SITE_DIR / "premium.html")


@app.get("/dashboard.html")
async def dashboard():
    return FileResponse(SITE_DIR / "dashboard.html")


@app.get("/account.html")
async def account():
    return FileResponse(SITE_DIR / "account.html")


app.mount("/css", StaticFiles(directory=SITE_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=SITE_DIR / "js"), name="js")


# ── Авторизация ─────────────────────────────────────────────────────────────

@app.get("/auth/login")
async def auth_login():
    if not CLIENT_ID:
        return RedirectResponse(url="/dashboard.html?error=oauth")
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
        "prompt": "none",
    }
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{DISCORD_AUTH_URL}?{q}")


@app.get("/auth/callback")
async def auth_callback(code: str = "", error: str = ""):
    if error or not code or not CLIENT_ID:
        return RedirectResponse(url="/dashboard.html?error=oauth")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            return RedirectResponse(url="/dashboard.html?error=oauth")
        token = r.json().get("access_token", "")
        user = await _discord_get(f"{DISCORD_API}/users/@me", token)
        if not user:
            return RedirectResponse(url="/dashboard.html?error=oauth")
    record = db.register_or_login(int(user["id"]), user["username"], user.get("avatar"))
    sess = _new_session(user, token)
    resp = RedirectResponse(url="/account.html?welcome=1" if record["is_new"] else "/dashboard.html")
    resp.set_cookie("lumi_token", sess, httponly=True, max_age=SESSION_TTL)
    return resp


@app.get("/auth/logout")
async def auth_logout(request: Request):
    token = _cookie_token(request)
    if token:
        SESSIONS.pop(token, None)
    resp = RedirectResponse(url="/")
    resp.delete_cookie("lumi_token")
    return resp


# ── API ─────────────────────────────────────────────────────────────────────

@app.get("/api/me")
async def api_me(request: Request):
    s = _require_session(request)
    rec = db.get_site_user(int(s["user_id"]))
    return {
        "user_id": int(s["user_id"]),
        "username": s["username"],
        "avatar": s["avatar"],
        "registered_at": (rec or {}).get("registered_at"),
        "last_login_at": (rec or {}).get("last_login_at"),
    }


# ── Покупка премиума и ключи ────────────────────────────────────────────────

@app.get("/api/promo/{code}")
async def api_promo(code: str):
    p = db.check_promo(code)
    if not p:
        raise HTTPException(status_code=404, detail="Промокод не найден")
    return {"code": p["code"], "percent": p["percent"]}


@app.post("/api/premium/buy")
async def api_premium_buy(request: Request):
    s = _require_session(request)
    body = await request.json()
    months = int(body.get("months", 0))
    if months not in PLANS:
        raise HTTPException(status_code=400, detail="Выберите тариф: 1 или 3 месяца")
    price = PLANS[months]
    discount = 0.0
    promo = None
    promo_code = (body.get("promo") or "").strip().upper()
    if promo_code:
        p = db.check_promo(promo_code)
        if not p:
            raise HTTPException(status_code=404, detail="Промокод не подходит")
        discount = round(price * p["percent"] / 100, 2)
        promo = p["code"]
    total = round(price - discount, 2)

    if not STRIPE_SECRET:
        raise HTTPException(status_code=500, detail="Stripe не настроен. Добавьте STRIPE_SECRET_KEY.")

    line_item = {
        "price_data": {
            "currency": "usd",
            "product_data": {"name": f"Lumi Premium — {months} мес."},
            "unit_amount": int(total * 100),
        },
        "quantity": 1,
    }
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[line_item],
        mode="payment",
        success_url=f"{DOMAIN}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{DOMAIN}/premium.html",
        metadata={
            "user_id": str(s["user_id"]),
            "months": str(months),
            "promo": promo or "",
            "amount": str(total),
        },
    )
    return {"url": session.url, "session_id": session.id}


@app.get("/payment/success")
async def payment_success(session_id: str = ""):
    if not session_id or not STRIPE_SECRET:
        return RedirectResponse(url="/premium.html?error=no_session")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return RedirectResponse(url="/premium.html?error=invalid_session")

    if session.payment_status != "paid":
        return RedirectResponse(url="/premium.html?error=not_paid")

    meta = session.metadata
    user_id = int(meta.get("user_id", 0))
    months = int(meta.get("months", 1))
    promo = meta.get("promo") or None
    amount = float(meta.get("amount", 0))

    if user_id:
        days = months * 30
        license_code = db.create_license(0, days, user_id)
        db.add_account_key(user_id, license_code, months, amount, promo)
        if promo:
            db.use_promo(promo)

    return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Lumi — Оплата прошла</title>
<style>
body{{background:#08090e;color:#e8eaf6;font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
.box{{text-align:center;max-width:440px;padding:40px}}
h1{{font-size:28px;margin-bottom:12px}}
p{{color:#8b90a8;margin-bottom:8px}}
.key{{background:#12141f;border:1px dashed #8b5cf6;color:#8b5cf6;font-family:monospace;font-size:18px;padding:16px;border-radius:12px;margin:20px 0;letter-spacing:1px;user-select:all}}
a{{color:#3b82f6;text-decoration:none;font-weight:700}}
a:hover{{text-decoration:underline}}
</style></head>
<body><div class="box">
<h1>Оплата прошла!</h1>
<p>Твой ключ сохранён в личном кабинете.</p>
<div class="key">{license_code}</div>
<p>Активируй в Discord: <b>!активировать КОД</b></p>
<a href="/account.html">Открыть кабинет →</a>
</div></body></html>""")


@app.get("/api/account/keys")
async def api_account_keys(request: Request):
    s = _require_session(request)
    keys = db.get_account_keys(int(s["user_id"]))
    out = []
    for k in keys:
        lic = db.get_license(k["license_code"])
        out.append({
            "license": k["license_code"],
            "months": k["months"],
            "amount": k["amount"],
            "promo": k["promo"],
            "purchased_at": k["purchased_at"],
            "activated": lic is None,
        })
    return out


@app.get("/api/premium/plans")
async def api_premium_plans():
    return [{"months": m, "price": p} for m, p in PLANS.items()]


async def _user_admin_guilds(s: dict) -> list[dict]:
    """Гильдии юзера, где он админ/владелец и бот в них есть."""
    user_guilds = await _discord_get(f"{DISCORD_API}/users/@me/guilds", s["access_token"])
    if not user_guilds:
        return []
    out = []
    for g in user_guilds:
        if (int(g.get("permissions", 0)) & ADMIN_PERM) != ADMIN_PERM:
            continue
        if _bot_get(f"/guilds/{g['id']}"):
            out.append({"id": int(g["id"]), "name": g["name"], "icon": g.get("icon")})
    return sorted(out, key=lambda x: x["name"].lower())


@app.get("/api/servers")
async def api_servers(request: Request):
    s = _require_session(request)
    return await _user_admin_guilds(s)


@app.get("/api/server/{gid}")
async def api_server(gid: int, request: Request):
    s = _require_session(request)
    await _check_admin(gid, s)
    welcome = db.get_welcome_config(gid)
    automod = db.get_automod(gid)
    level_roles = db.get_level_roles(gid)
    return {
        "guild_id": gid,
        "welcome": {
            "enabled": bool(welcome.get("enabled")),
            "card_enabled": bool(welcome.get("card_enabled", 1)),
            "channel_id": welcome.get("channel_id"),
            "rules_text": welcome.get("rules_text") or "",
            "guest_role_id": welcome.get("guest_role_id"),
        },
        "automod": {
            "enabled": bool(automod.get("enabled")),
            "bad_words": automod.get("bad_words", []),
            "min_interval": automod.get("min_interval", 5.0),
        },
        "level_roles": [{"level": r["level"], "role_id": r["role_id"]} for r in level_roles],
    }


@app.get("/api/server/{gid}/assets")
async def api_server_assets(gid: int, request: Request):
    s = _require_session(request)
    await _check_admin(gid, s)
    channels = await _bot_get(f"/guilds/{gid}/channels")
    roles = await _bot_get(f"/guilds/{gid}/roles")
    out_channels = []
    if isinstance(channels, list):
        for c in channels:
            if c.get("type") in (0, 5):  # text, announcement
                out_channels.append({"id": int(c["id"]), "name": c["name"]})
    out_roles = []
    if isinstance(roles, list):
        for r in roles:
            if r.get("name") != "@everyone":
                out_roles.append({"id": int(r["id"]), "name": r["name"]})
    return {"channels": out_channels, "roles": out_roles}


@app.post("/api/server/{gid}/save")
async def api_server_save(gid: int, request: Request):
    s = _require_session(request)
    await _check_admin(gid, s)
    body = await request.json()
    if "welcome" in body:
        w = body["welcome"]
        db.save_welcome_config(
            gid,
            channel_id=int(w["channel_id"]) if w.get("channel_id") else None,
            rules_text=w.get("rules_text") or None,
            guest_role_id=int(w["guest_role_id"]) if w.get("guest_role_id") else None,
            enabled=bool(w.get("enabled", True)),
            card_enabled=bool(w.get("card_enabled", True)),
        )
    if "automod" in body:
        a = body["automod"]
        db.save_automod(
            gid,
            enabled=bool(a.get("enabled", False)),
            bad_words=a.get("bad_words", []),
            min_interval=float(a.get("min_interval", 5.0)),
        )
    if "level_roles" in body:
        _clear_level_roles(gid)
        for item in body["level_roles"]:
            try:
                lvl = int(item["level"])
                rid = int(item["role_id"])
                if 1 <= lvl <= 100 and rid > 0:
                    db.set_level_role(gid, lvl, rid)
            except (KeyError, TypeError, ValueError):
                continue
    return {"ok": True}


def _clear_level_roles(gid: int):
    with db._conn() as con:
        con.execute("DELETE FROM level_roles WHERE guild_id = ?", (gid,))


async def _check_admin(gid: int, s: dict):
    guilds = await _user_admin_guilds(s)
    ids = {g["id"] for g in guilds}
    if gid not in ids:
        raise HTTPException(status_code=404, detail="Сервер не найден")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")