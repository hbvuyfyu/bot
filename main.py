#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AK Jumper Bot - Main Entry Point
Organized structure for Railway deployment with Neon PostgreSQL
"""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from config import BOT_TOKEN, ADMIN_IDS, SUPPORT_USER, MAX_WORKERS
from database import get_db, return_db, cache_clear
from handlers.database_operations import *
from datetime import datetime
import requests
import random
import uuid
import time
from concurrent.futures import ThreadPoolExecutor

# ==================== Logging ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== Executor ====================
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# ==================== API Send Functions ====================

def send_af(pkg: str, dev_key: str, gaid: str, af_uid: str, event_name: str,
            revenue: float = None, proxy: dict = None, platform: str = "android",
            idfa: str = None, idfv: str = None):
    if not pkg or pkg == "None" or pkg is None:
        return 400, "Error: Package name is required"
    if not dev_key:
        return 400, "Error: Dev Key is required"

    url = f"https://api2.appsflyer.com/inappevent/{pkg}"
    current_ts = int(time.time() * 1000)

    DEVICE_MODEL = "SM-S911B"
    OS_VERSION = "Android 14"
    SDK_VERSION = "6.15.0"
    APP_VERSION = "2.3.0"

    payload = {
        "appsflyer_id": af_uid,
        "advertising_id": gaid,
        "eventName": event_name,
        "eventTime": current_ts,
        "eventValue": {},
        "device_model": DEVICE_MODEL,
        "os_version": OS_VERSION,
        "sdk_version": SDK_VERSION,
        "app_version_name": APP_VERSION,
        "network": "WiFi",
        "language": "en-US",
        "timezone": "Asia/Riyadh"
    }

    if revenue:
        payload["eventRevenue"] = str(revenue)
        payload["eventCurrency"] = "USD"
        payload["eventValue"] = {
            "af_content_id": f"combo_{random.randint(1,50)}",
            "af_content_type": "purchase",
            "af_receipt_id": str(uuid.uuid4()),
            "af_transaction_id": str(uuid.uuid4()),
            "af_currency": "USD",
            "af_price": str(revenue)
        }
    else:
        level_num = ''.join(filter(str.isdigit, event_name))
        if level_num:
            payload["eventValue"] = {
                "af_level": level_num,
                "af_score": str(random.randint(1000, 50000)),
                "af_duration": str(random.randint(30, 300))
            }

    headers = {
        "Authentication": dev_key,
        "User-Agent": f"AppsFlyer-Android-SDK/{SDK_VERSION} (Linux; Android 14; {DEVICE_MODEL})",
        "Content-Type": "application/json",
    }

    try:
        if proxy:
            r = requests.post(url, json=payload, headers=headers, timeout=30, proxies=proxy)
        else:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
        return r.status_code, r.text
    except Exception as e:
        return 500, str(e)


def send_adj(app_token: str, event_token: str, gps_adid: str, proxy: dict = None):
    url = "https://s2s.adjust.com/event"
    params = {
        "app_token": app_token,
        "event_token": event_token,
        "gps_adid": gps_adid,
        "s2s": "1",
        "created_at": int(time.time())
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    try:
        if proxy:
            r = requests.get(url, params=params, headers=headers, timeout=30, proxies=proxy)
        else:
            r = requests.get(url, params=params, headers=headers, timeout=30)
        if r.status_code == 200:
            return 200, r.text
        return r.status_code, r.text
    except Exception as e:
        return 500, str(e)


def send_singular(event_name, aifa, uid, package, app_key, level=None, proxy=None, platform="android", idfa=None, idfv=None):
    base_url = "https://s2s.singular.net/api/v1/evt"
    params = {
        "a": app_key,
        "p": "Android",
        "i": package,
        "aifa": aifa,
        "u": uid if uid else "",
        "utime": int(time.time()),
        "n": event_name
    }
    params = {k: v for k, v in params.items() if v}
    headers = {
        "User-Agent": "SingularS2S/1.0",
        "Accept": "application/json"
    }

    try:
        if proxy:
            r = requests.get(base_url, params=params, headers=headers, timeout=30, proxies=proxy)
        else:
            r = requests.get(base_url, params=params, headers=headers, timeout=30)
        if r.status_code == 200:
            return 200, r.text
        return r.status_code, r.text
    except Exception as e:
        return 500, str(e)


# ==================== Start Command ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uname = update.effective_user.username or ""
    name = update.effective_user.first_name or ""

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, username, name, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET username = %s, name = %s
            """, (uid, uname, name, datetime.now(), uname, name))
            cur.execute("INSERT INTO user_platform (user_id, platform) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (uid, "android"))
            conn.commit()
    finally:
        return_db(conn)

    if not is_allowed(uid):
        await update.message.reply_text(
            f"Access Denied\n\nYou are not registered.\nContact: {SUPPORT_USER}",
            parse_mode="Markdown"
        )
        return

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT banned FROM users WHERE user_id = %s", (uid,))
            result = cur.fetchone()
            if result and result['banned'] == 1:
                await update.message.reply_text(f"You are banned\n\nContact: {SUPPORT_USER}", parse_mode="Markdown")
                return
    finally:
        return_db(conn)

    current_platform = get_user_platform(uid)
    platform_emoji = "🤖" if current_platform == "android" else "🍎"

    kb = []
    if is_admin(uid):
        kb.append([InlineKeyboardButton("Admin Panel", callback_data="admin_panel")])
    kb.append([InlineKeyboardButton("AppsFlyer", callback_data="af")])
    kb.append([InlineKeyboardButton("Adjust", callback_data="adj")])
    kb.append([InlineKeyboardButton("Singular", callback_data="singular")])
    kb.append([InlineKeyboardButton("Farm", callback_data="jumper_farm")])
    kb.append([InlineKeyboardButton("Proxy Settings", callback_data="proxy_settings")])
    kb.append([InlineKeyboardButton(f"{platform_emoji} Platform: {current_platform.upper()}", callback_data="select_platform")])

    await update.message.reply_text(
        f"AK Jumper Bot\n\nSelect a service:\n\nPlatform: {platform_emoji} {current_platform.upper()}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    current_platform = get_user_platform(uid)
    platform_emoji = "🤖" if current_platform == "android" else "🍎"

    kb = []
    if is_admin(uid):
        kb.append([InlineKeyboardButton("Admin Panel", callback_data="admin_panel")])
    kb.append([InlineKeyboardButton("AppsFlyer", callback_data="af")])
    kb.append([InlineKeyboardButton("Adjust", callback_data="adj")])
    kb.append([InlineKeyboardButton("Singular", callback_data="singular")])
    kb.append([InlineKeyboardButton("Farm", callback_data="jumper_farm")])
    kb.append([InlineKeyboardButton("Proxy Settings", callback_data="proxy_settings")])
    kb.append([InlineKeyboardButton(f"{platform_emoji} Platform: {current_platform.upper()}", callback_data="select_platform")])

    await query.edit_message_text(
        f"AK Jumper Bot\n\nSelect a service:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )
    return -1


# ==================== Admin Panel ====================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Not authorized", parse_mode="Markdown")
        return -1

    kb = [
        [InlineKeyboardButton("Users", callback_data="admin_users")],
        [InlineKeyboardButton("Add User", callback_data="admin_add_user")],
        [InlineKeyboardButton("Remove User", callback_data="admin_remove_user")],
        [InlineKeyboardButton("Ban User", callback_data="admin_ban")],
        [InlineKeyboardButton("Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton("Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("Back", callback_data="main")]
    ]
    await query.edit_message_text("Admin Panel", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return -1


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) FROM allowed_users")
            total_allowed = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) FROM users WHERE banned=1")
            total_banned = cur.fetchone()['count']
            cur.execute("SELECT COALESCE(SUM(total_requests), 0) FROM users")
            total_requests = cur.fetchone()['coalesce']
    finally:
        return_db(conn)

    txt = f"""Statistics

Total Users: {total_users}
Allowed Users: {total_allowed}
Banned Users: {total_banned}
Total Requests: {total_requests}"""

    await query.edit_message_text(txt, parse_mode="Markdown")
    await asyncio.sleep(2)
    await admin_panel(update, context)
    return -1


# ==================== Proxy Settings ====================

async def proxy_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    pinfo = get_proxy_info(uid)
    status = "No proxy configured" if not pinfo else f"Proxy: {pinfo['proxy_type']} {pinfo['proxy_host']}:{pinfo['proxy_port']}"

    kb = [
        [InlineKeyboardButton("Add Proxy", callback_data="proxy_add")],
        [InlineKeyboardButton("Delete Proxy", callback_data="proxy_del")],
        [InlineKeyboardButton("Test Proxy", callback_data="proxy_test")],
        [InlineKeyboardButton("Back", callback_data="main")]
    ]
    await query.edit_message_text(
        f"Proxy Settings\n\n{status}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )
    return "PROXY_MAIN"


async def proxy_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("HTTP/HTTPS", callback_data="proxy_type_http")],
        [InlineKeyboardButton("SOCKS5", callback_data="proxy_type_socks5")],
        [InlineKeyboardButton("Back", callback_data="proxy_settings")]
    ]
    await query.edit_message_text("Select proxy type:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return "PROXY_TYPE"


async def proxy_type_http(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["proxy_type"] = "http"
    await query.edit_message_text("Enter IP:Port\nExample: `192.168.1.100:8080`", parse_mode="Markdown")
    return "PROXY_IP_PORT"


async def proxy_type_socks5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["proxy_type"] = "socks5"
    await query.edit_message_text("Enter IP:Port\nExample: `192.168.1.100:1080`", parse_mode="Markdown")
    return "PROXY_IP_PORT"


async def proxy_ip_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ip_port = update.message.text.strip()
    try:
        if ":" not in ip_port:
            await update.message.reply_text("Invalid format. Use: `ip:port`", parse_mode="Markdown")
            return "PROXY_IP_PORT"
        host, port = ip_port.split(":", 1)
        port = int(port)
        context.user_data["proxy_host"] = host
        context.user_data["proxy_port"] = port

        kb = [
            [InlineKeyboardButton("No authentication", callback_data="proxy_no_auth")],
            [InlineKeyboardButton("Add authentication", callback_data="proxy_need_auth")],
            [InlineKeyboardButton("Back", callback_data="proxy_add")]
        ]
        await update.message.reply_text(
            f"Set: `{host}:{port}`\n\nDo you need authentication?",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return "PROXY_AUTH"
    except ValueError:
        await update.message.reply_text("Port must be a number", parse_mode="Markdown")
        return "PROXY_IP_PORT"


async def proxy_no_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    proxy_type = context.user_data.get("proxy_type", "http")
    host = context.user_data.get("proxy_host")
    port = context.user_data.get("proxy_port")

    save_proxy(uid, proxy_type, host, port, "", "")

    # Test proxy
    if proxy_type == "socks5":
        proxy_url = f"socks5://{host}:{port}"
        proxies = {"socks5": proxy_url, "http": proxy_url, "https": proxy_url}
    else:
        proxy_url = f"http://{host}:{port}"
        proxies = {"http": proxy_url, "https": proxy_url}

    try:
        r = requests.get('https://api.ipify.org?format=json', proxies=proxies, timeout=20)
        if r.status_code == 200:
            ip = r.json().get('ip', 'Unknown')
            await query.message.reply_text(f"Proxy saved and working!\nIP: {ip}", parse_mode="Markdown")
        else:
            await query.message.reply_text("Proxy saved but test failed", parse_mode="Markdown")
    except Exception:
        await query.message.reply_text("Proxy saved but connection failed", parse_mode="Markdown")

    for key in ['proxy_type', 'proxy_host', 'proxy_port']:
        context.user_data.pop(key, None)

    await main_menu(update, context)
    return -1


async def proxy_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    delete_proxy(query.from_user.id)
    await query.edit_message_text("Proxy deleted", parse_mode="Markdown")
    await asyncio.sleep(1)
    await main_menu(update, context)
    return -1


# ==================== Platform Selection ====================

async def select_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    current_platform = get_user_platform(user_id)

    kb = [
        [InlineKeyboardButton("Android", callback_data="set_platform_android")],
        [InlineKeyboardButton("iOS", callback_data="set_platform_ios")],
        [InlineKeyboardButton("Back", callback_data="main")]
    ]
    await query.edit_message_text(
        f"Current: {current_platform.upper()}\n\nSelect platform:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )
    return -1


async def set_platform_android(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    set_user_platform(query.from_user.id, "android")
    await query.edit_message_text("Set to Android", parse_mode="Markdown")
    await asyncio.sleep(1)
    await main_menu(update, context)
    return -1


async def set_platform_ios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    set_user_platform(query.from_user.id, "ios")
    await query.edit_message_text("Set to iOS", parse_mode="Markdown")
    await asyncio.sleep(1)
    await main_menu(update, context)
    return -1


# ==================== Main ====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Proxy Conversation
    proxy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(proxy_settings, pattern="^proxy_settings$")],
        states={
            "PROXY_MAIN": [
                CallbackQueryHandler(proxy_add, pattern="^proxy_add$"),
                CallbackQueryHandler(proxy_del, pattern="^proxy_del$"),
                CallbackQueryHandler(main_menu, pattern="^main$")
            ],
            "PROXY_TYPE": [
                CallbackQueryHandler(proxy_type_http, pattern="^proxy_type_http$"),
                CallbackQueryHandler(proxy_type_socks5, pattern="^proxy_type_socks5$")
            ],
            "PROXY_IP_PORT": [MessageHandler(filters.TEXT & ~filters.COMMAND, proxy_ip_port)],
            "PROXY_AUTH": [
                CallbackQueryHandler(proxy_no_auth, pattern="^proxy_no_auth$")
            ],
        },
        fallbacks=[],
        allow_reentry=True
    )

    app.add_handler(proxy_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main$"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(select_platform, pattern="^select_platform$"))
    app.add_handler(CallbackQueryHandler(set_platform_android, pattern="^set_platform_android$"))
    app.add_handler(CallbackQueryHandler(set_platform_ios, pattern="^set_platform_ios$"))

    print("=" * 60)
    print("AK Bot Started - PostgreSQL Version")
    print(f"Admin IDs: {ADMIN_IDS}")
    print(f"Support: {SUPPORT_USER}")
    print("=" * 60)
    app.run_polling()


if __name__ == "__main__":
    main()
