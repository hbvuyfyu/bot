#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from config import BOT_TOKEN, ADMIN_IDS, SUPPORT_USER, MAX_WORKERS
from database import get_db, return_db, cache_clear
from database_operations import *
from datetime import datetime
import requests
import random
import uuid
import time
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# ==================== API Send Functions ====================

def send_af(pkg, dev_key, gaid, af_uid, event_name, revenue=None, proxy=None, platform="android", idfa=None, idfv=None):
    if not pkg or pkg == "None" or pkg is None:
        return 400, "Error: Package name is required"
    if not dev_key:
        return 400, "Error: Dev Key is required"
    url = f"https://api2.appsflyer.com/inappevent/{pkg}"
    current_ts = int(time.time() * 1000)
    payload = {
        "appsflyer_id": af_uid,
        "advertising_id": gaid,
        "eventName": event_name,
        "eventTime": current_ts,
        "eventValue": {},
        "device_model": "SM-S911B",
        "os_version": "Android 14",
        "sdk_version": "6.15.0",
        "app_version_name": "2.3.0",
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
        "User-Agent": "AppsFlyer-Android-SDK/6.15.0 (Linux; Android 14; SM-S911B)",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30, proxies=proxy)
        return r.status_code, r.text
    except Exception as e:
        return 500, str(e)


def send_adj(app_token, event_token, gps_adid, proxy=None):
    url = "https://s2s.adjust.com/event"
    params = {
        "app_token": app_token,
        "event_token": event_token,
        "gps_adid": gps_adid,
        "s2s": "1",
        "created_at": int(time.time())
    }
    try:
        r = requests.get(url, params=params, timeout=30, proxies=proxy)
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
    try:
        r = requests.get(base_url, params=params, timeout=30, proxies=proxy)
        return r.status_code, r.text
    except Exception as e:
        return 500, str(e)


# ==================== Start / Main Menu ====================

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
        await update.message.reply_text(f"Access Denied\n\nContact: {SUPPORT_USER}")
        return

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT banned FROM users WHERE user_id = %s", (uid,))
            result = cur.fetchone()
            if result and result['banned'] == 1:
                await update.message.reply_text(f"You are banned\n\nContact: {SUPPORT_USER}")
                return
    finally:
        return_db(conn)

    await show_main_menu_message(update, context, uid)


async def show_main_menu_message(update, context, uid):
    current_platform = get_user_platform(uid)
    platform_emoji = "🤖" if current_platform == "android" else "🍎"
    kb = []
    if is_admin(uid):
        kb.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    kb.append([InlineKeyboardButton("📱 AppsFlyer", callback_data="af")])
    kb.append([InlineKeyboardButton("📊 Adjust", callback_data="adj")])
    kb.append([InlineKeyboardButton("🔵 Singular", callback_data="singular")])
    kb.append([InlineKeyboardButton("🌾 Farm", callback_data="jumper_farm")])
    kb.append([InlineKeyboardButton("🔗 Proxy Settings", callback_data="proxy_settings")])
    kb.append([InlineKeyboardButton(f"{platform_emoji} Platform: {current_platform.upper()}", callback_data="select_platform")])
    text = f"🤖 AK Jumper Bot\n\nSelect a service:\nPlatform: {platform_emoji} {current_platform.upper()}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_main_menu_message(update, context, query.from_user.id)
    return ConversationHandler.END


# ==================== AppsFlyer ====================

async def af_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    games = get_all_games_af()
    if not games:
        await query.edit_message_text("No AppsFlyer games found.")
        return
    kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"af_game_{g['id']}")] for g in games]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="main")])
    await query.edit_message_text("📱 AppsFlyer\n\nSelect a game:", reply_markup=InlineKeyboardMarkup(kb))


async def af_game_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = int(query.data.split("_")[-1])
    context.user_data["af_game_id"] = game_id
    kb = [
        [InlineKeyboardButton("🎯 Send Event", callback_data="af_send_event")],
        [InlineKeyboardButton("💰 Send Purchase", callback_data="af_send_purchase")],
        [InlineKeyboardButton("🔙 Back", callback_data="af")]
    ]
    await query.edit_message_text("Select action:", reply_markup=InlineKeyboardMarkup(kb))


async def af_send_event_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = context.user_data.get("af_game_id")
    events = get_af_events(game_id, purchase_only=False)
    if not events:
        await query.edit_message_text("No events found for this game.")
        return
    kb = [[InlineKeyboardButton(e['display_name'], callback_data=f"af_ev_{e['id']}")] for e in events]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data=f"af_game_{game_id}")])
    await query.edit_message_text("Select event:", reply_markup=InlineKeyboardMarkup(kb))


async def af_send_purchase_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = context.user_data.get("af_game_id")
    events = get_af_events(game_id, purchase_only=True)
    if not events:
        await query.edit_message_text("No purchase events found.")
        return
    kb = [[InlineKeyboardButton(e['display_name'], callback_data=f"af_purchase_{e['id']}")] for e in events]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data=f"af_game_{game_id}")])
    await query.edit_message_text("Select purchase event:", reply_markup=InlineKeyboardMarkup(kb))


async def af_ask_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split("_")[-1])
    context.user_data["af_event_id"] = event_id
    context.user_data["af_mode"] = "event"
    await query.edit_message_text(
        "Enter GAID and AF_UID\n\nFormat:\n`gaid|af_uid`\n\nExample:\n`abc123|xyz456`",
        parse_mode="Markdown"
    )
    return "AF_IDS"


async def af_ask_purchase_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split("_")[-1])
    context.user_data["af_event_id"] = event_id
    context.user_data["af_mode"] = "purchase"
    await query.edit_message_text(
        "Enter GAID, AF_UID and Revenue\n\nFormat:\n`gaid|af_uid|revenue`\n\nExample:\n`abc123|xyz456|9.99`",
        parse_mode="Markdown"
    )
    return "AF_IDS"


async def af_receive_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split("|")
    uid = update.effective_user.id
    mode = context.user_data.get("af_mode", "event")

    if mode == "purchase" and len(parts) < 3:
        await update.message.reply_text("Invalid format. Use: `gaid|af_uid|revenue`", parse_mode="Markdown")
        return "AF_IDS"
    if mode == "event" and len(parts) < 2:
        await update.message.reply_text("Invalid format. Use: `gaid|af_uid`", parse_mode="Markdown")
        return "AF_IDS"

    gaid = parts[0].strip()
    af_uid = parts[1].strip()
    revenue = float(parts[2].strip()) if mode == "purchase" and len(parts) > 2 else None

    game_id = context.user_data.get("af_game_id")
    event_id = context.user_data.get("af_event_id")

    # Get game info
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games_af WHERE id = %s", (game_id,))
            game = cur.fetchone()
            cur.execute("SELECT * FROM events_af WHERE id = %s", (event_id,))
            event = cur.fetchone()
    finally:
        return_db(conn)

    if not game or not event:
        await update.message.reply_text("Game or event not found.")
        return ConversationHandler.END

    proxy = get_proxy_for_user(uid)
    msg = await update.message.reply_text("⏳ Sending...")
    status, response = send_af(game['package'], game['dev_key'], gaid, af_uid, event['event_name'], revenue, proxy)
    increment_user_requests(uid)

    result = "✅ Success" if status == 200 else f"❌ Failed ({status})"
    await msg.edit_text(f"{result}\n\nEvent: {event['display_name']}\nResponse: {response[:200]}")
    return ConversationHandler.END


# ==================== Adjust ====================

async def adj_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    games = get_all_games_adj()
    if not games:
        await query.edit_message_text("No Adjust games found.")
        return
    kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"adj_game_{g['id']}")] for g in games]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="main")])
    await query.edit_message_text("📊 Adjust\n\nSelect a game:", reply_markup=InlineKeyboardMarkup(kb))


async def adj_game_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = int(query.data.split("_")[-1])
    context.user_data["adj_game_id"] = game_id
    events = get_adj_events(game_id)
    if not events:
        await query.edit_message_text("No events found.")
        return
    kb = [[InlineKeyboardButton(e['display_name'], callback_data=f"adj_ev_{e['id']}")] for e in events]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="adj")])
    await query.edit_message_text("Select event:", reply_markup=InlineKeyboardMarkup(kb))


async def adj_ask_gps_adid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split("_")[-1])
    context.user_data["adj_event_id"] = event_id
    await query.edit_message_text("Enter GPS_ADID (Google Advertising ID):", parse_mode="Markdown")
    return "ADJ_GPS"


async def adj_receive_gps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gps_adid = update.message.text.strip()
    uid = update.effective_user.id
    game_id = context.user_data.get("adj_game_id")
    event_id = context.user_data.get("adj_event_id")

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games_adj WHERE id = %s", (game_id,))
            game = cur.fetchone()
            cur.execute("SELECT * FROM events_adj WHERE id = %s", (event_id,))
            event = cur.fetchone()
    finally:
        return_db(conn)

    if not game or not event:
        await update.message.reply_text("Game or event not found.")
        return ConversationHandler.END

    proxy = get_proxy_for_user(uid)
    msg = await update.message.reply_text("⏳ Sending...")
    status, response = send_adj(game['app_token'], event['event_token'], gps_adid, proxy)
    increment_user_requests(uid)

    result = "✅ Success" if status == 200 else f"❌ Failed ({status})"
    await msg.edit_text(f"{result}\n\nEvent: {event['display_name']}\nResponse: {response[:200]}")
    return ConversationHandler.END


# ==================== Singular ====================

async def singular_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    games = get_all_games_singular()
    if not games:
        await query.edit_message_text("No Singular games found.")
        return
    kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"sg_game_{g['id']}")] for g in games]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="main")])
    await query.edit_message_text("🔵 Singular\n\nSelect a game:", reply_markup=InlineKeyboardMarkup(kb))


async def sg_game_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = int(query.data.split("_")[-1])
    context.user_data["sg_game_id"] = game_id
    events = get_singular_events(game_id)
    if not events:
        await query.edit_message_text("No events found.")
        return
    kb = [[InlineKeyboardButton(e['display_name'], callback_data=f"sg_ev_{e['id']}")] for e in events]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="singular")])
    await query.edit_message_text("Select event:", reply_markup=InlineKeyboardMarkup(kb))


async def sg_ask_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split("_")[-1])
    context.user_data["sg_event_id"] = event_id
    await query.edit_message_text(
        "Enter AIFA and UID\n\nFormat:\n`aifa|uid`\n\nExample:\n`abc123|xyz456`",
        parse_mode="Markdown"
    )
    return "SG_IDS"


async def sg_receive_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split("|")
    if len(parts) < 2:
        await update.message.reply_text("Invalid format. Use: `aifa|uid`", parse_mode="Markdown")
        return "SG_IDS"

    aifa = parts[0].strip()
    uid_val = parts[1].strip()
    uid = update.effective_user.id
    game_id = context.user_data.get("sg_game_id")
    event_id = context.user_data.get("sg_event_id")

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games_singular WHERE id = %s", (game_id,))
            game = cur.fetchone()
            cur.execute("SELECT * FROM events_singular WHERE id = %s", (event_id,))
            event = cur.fetchone()
    finally:
        return_db(conn)

    if not game or not event:
        await update.message.reply_text("Game or event not found.")
        return ConversationHandler.END

    proxy = get_proxy_for_user(uid)
    msg = await update.message.reply_text("⏳ Sending...")
    status, response = send_singular(event['event_name'], aifa, uid_val, game['package'], game['app_key'], proxy=proxy)
    increment_user_requests(uid)

    result = "✅ Success" if status == 200 else f"❌ Failed ({status})"
    await msg.edit_text(f"{result}\n\nEvent: {event['display_name']}\nResponse: {response[:200]}")
    return ConversationHandler.END


# ==================== Farm ====================

async def farm_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM farm_tasks WHERE user_id = %s ORDER BY created_date DESC LIMIT 10", (uid,))
            tasks = cur.fetchall()
    finally:
        return_db(conn)

    kb = [
        [InlineKeyboardButton("➕ New Farm Task", callback_data="farm_new")],
        [InlineKeyboardButton("🔙 Back", callback_data="main")]
    ]

    if tasks:
        task_lines = "\n".join([f"• {t['task_name']} [{t['status']}]" for t in tasks])
        text = f"🌾 Farm\n\nYour tasks:\n{task_lines}"
    else:
        text = "🌾 Farm\n\nNo tasks yet."

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))


async def farm_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer Farm", callback_data="farm_af")],
        [InlineKeyboardButton("📊 Adjust Farm", callback_data="farm_adj")],
        [InlineKeyboardButton("🔵 Singular Farm", callback_data="farm_sg")],
        [InlineKeyboardButton("🔙 Back", callback_data="jumper_farm")]
    ]
    await query.edit_message_text("Select platform for farm:", reply_markup=InlineKeyboardMarkup(kb))


async def farm_select_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    platform = query.data.split("_")[-1]
    context.user_data["farm_platform"] = platform

    if platform == "af":
        games = get_all_games_af()
        prefix = "farm_game_af"
    elif platform == "adj":
        games = get_all_games_adj()
        prefix = "farm_game_adj"
    else:
        games = get_all_games_singular()
        prefix = "farm_game_sg"

    if not games:
        await query.edit_message_text("No games found.")
        return

    kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"{prefix}_{g['id']}")] for g in games]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="farm_new")])
    await query.edit_message_text("Select game for farm:", reply_markup=InlineKeyboardMarkup(kb))


async def farm_game_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    game_id = int(parts[-1])
    platform = parts[-2]
    context.user_data["farm_game_id"] = game_id
    context.user_data["farm_game_platform"] = platform
    await query.edit_message_text(
        "Enter farm details:\n\nFormat:\n`task_name|start_level|end_level|aifa_or_gaid`\n\nExample:\n`mytask|1|50|abc-123-xyz`",
        parse_mode="Markdown"
    )
    return "FARM_DETAILS"


async def farm_receive_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split("|")
    if len(parts) < 4:
        await update.message.reply_text("Invalid format. Use: `task_name|start|end|aifa_or_gaid`", parse_mode="Markdown")
        return "FARM_DETAILS"

    task_name = parts[0].strip()
    try:
        start_level = int(parts[1].strip())
        end_level = int(parts[2].strip())
    except ValueError:
        await update.message.reply_text("Levels must be numbers.", parse_mode="Markdown")
        return "FARM_DETAILS"

    aifa = parts[3].strip()
    uid = update.effective_user.id
    game_id = context.user_data.get("farm_game_id")
    platform = context.user_data.get("farm_game_platform", "af")

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO farm_tasks (user_id, task_name, platform, game_id, start_level, end_level,
                    current_level, status, created_date, aifa)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (uid, task_name, platform, game_id, start_level, end_level,
                  start_level, "pending", datetime.now(), aifa))
            conn.commit()
    finally:
        return_db(conn)

    await update.message.reply_text(f"✅ Farm task '{task_name}' created!\nLevels: {start_level} → {end_level}")
    return ConversationHandler.END


# ==================== Admin Panel ====================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Not authorized.")
        return ConversationHandler.END
    kb = [
        [InlineKeyboardButton("👥 Users List", callback_data="admin_users")],
        [InlineKeyboardButton("➕ Add User", callback_data="admin_add_user")],
        [InlineKeyboardButton("➖ Remove User", callback_data="admin_remove_user")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="main")]
    ]
    await query.edit_message_text("👑 Admin Panel", reply_markup=InlineKeyboardMarkup(kb))


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM users")
            total_users = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) as cnt FROM allowed_users")
            total_allowed = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) as cnt FROM users WHERE banned=1")
            total_banned = cur.fetchone()['cnt']
            cur.execute("SELECT COALESCE(SUM(total_requests), 0) as total FROM users")
            total_requests = cur.fetchone()['total']
    finally:
        return_db(conn)
    txt = f"📊 Statistics\n\nTotal Users: {total_users}\nAllowed Users: {total_allowed}\nBanned Users: {total_banned}\nTotal Requests: {total_requests}"
    kb = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = get_allowed_users()
    if not users:
        text = "No allowed users."
    else:
        lines = [f"• {u['user_id']} @{u['username'] or 'N/A'} - {u['name'] or 'N/A'}" for u in users[:20]]
        text = "👥 Allowed Users:\n\n" + "\n".join(lines)
    kb = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))


async def admin_ask_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Enter user ID to add:\n\nExample: `123456789`", parse_mode="Markdown")
    return "ADMIN_ADD_ID"


async def admin_do_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_uid = int(update.message.text.strip())
        add_allowed_user(new_uid, "", "", update.effective_user.id)
        await update.message.reply_text(f"✅ User {new_uid} added.")
    except ValueError:
        await update.message.reply_text("Invalid ID.")
    return ConversationHandler.END


async def admin_ask_remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Enter user ID to remove:", parse_mode="Markdown")
    return "ADMIN_REMOVE_ID"


async def admin_do_remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rem_uid = int(update.message.text.strip())
        remove_allowed_user(rem_uid)
        await update.message.reply_text(f"✅ User {rem_uid} removed.")
    except ValueError:
        await update.message.reply_text("Invalid ID.")
    return ConversationHandler.END


async def admin_ask_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Enter user ID to ban:", parse_mode="Markdown")
    return "ADMIN_BAN_ID"


async def admin_do_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ban_uid = int(update.message.text.strip())
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET banned=1 WHERE user_id=%s", (ban_uid,))
                conn.commit()
        finally:
            return_db(conn)
        await update.message.reply_text(f"🚫 User {ban_uid} banned.")
    except ValueError:
        await update.message.reply_text("Invalid ID.")
    return ConversationHandler.END


async def admin_ask_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Enter user ID to unban:", parse_mode="Markdown")
    return "ADMIN_UNBAN_ID"


async def admin_do_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        unban_uid = int(update.message.text.strip())
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET banned=0 WHERE user_id=%s", (unban_uid,))
                conn.commit()
        finally:
            return_db(conn)
        await update.message.reply_text(f"✅ User {unban_uid} unbanned.")
    except ValueError:
        await update.message.reply_text("Invalid ID.")
    return ConversationHandler.END


# ==================== Proxy Settings ====================

async def proxy_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    pinfo = get_proxy_info(uid)
    status = "No proxy configured" if not pinfo else f"Proxy: {pinfo['proxy_type']} {pinfo['proxy_host']}:{pinfo['proxy_port']}"
    kb = [
        [InlineKeyboardButton("➕ Add Proxy", callback_data="proxy_add")],
        [InlineKeyboardButton("🗑 Delete Proxy", callback_data="proxy_del")],
        [InlineKeyboardButton("🔙 Back", callback_data="main")]
    ]
    await query.edit_message_text(f"🔗 Proxy Settings\n\n{status}", reply_markup=InlineKeyboardMarkup(kb))
    return "PROXY_MAIN"


async def proxy_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("HTTP/HTTPS", callback_data="proxy_type_http")],
        [InlineKeyboardButton("SOCKS5", callback_data="proxy_type_socks5")],
        [InlineKeyboardButton("🔙 Back", callback_data="proxy_settings")]
    ]
    await query.edit_message_text("Select proxy type:", reply_markup=InlineKeyboardMarkup(kb))
    return "PROXY_TYPE"


async def proxy_type_http(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["proxy_type"] = "http"
    await query.edit_message_text("Enter `ip:port`\n\nExample: `192.168.1.1:8080`", parse_mode="Markdown")
    return "PROXY_IP_PORT"


async def proxy_type_socks5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["proxy_type"] = "socks5"
    await query.edit_message_text("Enter `ip:port`\n\nExample: `192.168.1.1:1080`", parse_mode="Markdown")
    return "PROXY_IP_PORT"


async def proxy_ip_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ip_port = update.message.text.strip()
    if ":" not in ip_port:
        await update.message.reply_text("Invalid format. Use: `ip:port`", parse_mode="Markdown")
        return "PROXY_IP_PORT"
    try:
        host, port = ip_port.split(":", 1)
        port = int(port)
        context.user_data["proxy_host"] = host
        context.user_data["proxy_port"] = port
        kb = [
            [InlineKeyboardButton("No auth", callback_data="proxy_no_auth")],
            [InlineKeyboardButton("With auth", callback_data="proxy_need_auth")]
        ]
        await update.message.reply_text(f"Set: `{host}:{port}`\n\nAuthentication?", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return "PROXY_AUTH"
    except ValueError:
        await update.message.reply_text("Port must be a number.")
        return "PROXY_IP_PORT"


async def proxy_no_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    proxy_type = context.user_data.get("proxy_type", "http")
    host = context.user_data.get("proxy_host")
    port = context.user_data.get("proxy_port")
    save_proxy(uid, proxy_type, host, port, "", "")
    await query.message.reply_text(f"✅ Proxy saved: {proxy_type} {host}:{port}")
    for key in ['proxy_type', 'proxy_host', 'proxy_port']:
        context.user_data.pop(key, None)
    return ConversationHandler.END


async def proxy_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    delete_proxy(query.from_user.id)
    await query.edit_message_text("✅ Proxy deleted.")
    return ConversationHandler.END


# ==================== Platform Selection ====================

async def select_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    current = get_user_platform(query.from_user.id)
    kb = [
        [InlineKeyboardButton("🤖 Android", callback_data="set_platform_android")],
        [InlineKeyboardButton("🍎 iOS", callback_data="set_platform_ios")],
        [InlineKeyboardButton("🔙 Back", callback_data="main")]
    ]
    await query.edit_message_text(f"Current: {current.upper()}\n\nSelect platform:", reply_markup=InlineKeyboardMarkup(kb))


async def set_platform_android(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    set_user_platform(query.from_user.id, "android")
    await query.edit_message_text("✅ Set to Android")
    await asyncio.sleep(1)
    await main_menu(update, context)


async def set_platform_ios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    set_user_platform(query.from_user.id, "ios")
    await query.edit_message_text("✅ Set to iOS")
    await asyncio.sleep(1)
    await main_menu(update, context)


# ==================== Main ====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # AppsFlyer Conversation
    af_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(af_menu, pattern="^af$")],
        states={
            "AF_IDS": [MessageHandler(filters.TEXT & ~filters.COMMAND, af_receive_ids)],
        },
        fallbacks=[CallbackQueryHandler(main_menu, pattern="^main$")],
        allow_reentry=True
    )

    # Adjust Conversation
    adj_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adj_menu, pattern="^adj$")],
        states={
            "ADJ_GPS": [MessageHandler(filters.TEXT & ~filters.COMMAND, adj_receive_gps)],
        },
        fallbacks=[CallbackQueryHandler(main_menu, pattern="^main$")],
        allow_reentry=True
    )

    # Singular Conversation
    sg_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(singular_menu, pattern="^singular$")],
        states={
            "SG_IDS": [MessageHandler(filters.TEXT & ~filters.COMMAND, sg_receive_ids)],
        },
        fallbacks=[CallbackQueryHandler(main_menu, pattern="^main$")],
        allow_reentry=True
    )

    # Farm Conversation
    farm_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(farm_menu, pattern="^jumper_farm$")],
        states={
            "FARM_DETAILS": [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_receive_details)],
        },
        fallbacks=[CallbackQueryHandler(main_menu, pattern="^main$")],
        allow_reentry=True
    )

    # Proxy Conversation
    proxy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(proxy_settings, pattern="^proxy_settings$")],
        states={
            "PROXY_MAIN": [
                CallbackQueryHandler(proxy_add, pattern="^proxy_add$"),
                CallbackQueryHandler(proxy_del, pattern="^proxy_del$"),
            ],
            "PROXY_TYPE": [
                CallbackQueryHandler(proxy_type_http, pattern="^proxy_type_http$"),
                CallbackQueryHandler(proxy_type_socks5, pattern="^proxy_type_socks5$"),
            ],
            "PROXY_IP_PORT": [MessageHandler(filters.TEXT & ~filters.COMMAND, proxy_ip_port)],
            "PROXY_AUTH": [CallbackQueryHandler(proxy_no_auth, pattern="^proxy_no_auth$")],
        },
        fallbacks=[CallbackQueryHandler(main_menu, pattern="^main$")],
        allow_reentry=True
    )

    # Admin Conversation
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        states={
            "ADMIN_ADD_ID": [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_do_add_user)],
            "ADMIN_REMOVE_ID": [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_do_remove_user)],
            "ADMIN_BAN_ID": [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_do_ban)],
            "ADMIN_UNBAN_ID": [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_do_unban)],
        },
        fallbacks=[CallbackQueryHandler(main_menu, pattern="^main$")],
        allow_reentry=True
    )

    app.add_handler(af_conv)
    app.add_handler(adj_conv)
    app.add_handler(sg_conv)
    app.add_handler(farm_conv)
    app.add_handler(proxy_conv)
    app.add_handler(admin_conv)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main$"))
    app.add_handler(CallbackQueryHandler(select_platform, pattern="^select_platform$"))
    app.add_handler(CallbackQueryHandler(set_platform_android, pattern="^set_platform_android$"))
    app.add_handler(CallbackQueryHandler(set_platform_ios, pattern="^set_platform_ios$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_ask_add_user, pattern="^admin_add_user$"))
    app.add_handler(CallbackQueryHandler(admin_ask_remove_user, pattern="^admin_remove_user$"))
    app.add_handler(CallbackQueryHandler(admin_ask_ban, pattern="^admin_ban$"))
    app.add_handler(CallbackQueryHandler(admin_ask_unban, pattern="^admin_unban$"))
    app.add_handler(CallbackQueryHandler(af_game_select, pattern="^af_game_\\d+$"))
    app.add_handler(CallbackQueryHandler(af_send_event_menu, pattern="^af_send_event$"))
    app.add_handler(CallbackQueryHandler(af_send_purchase_menu, pattern="^af_send_purchase$"))
    app.add_handler(CallbackQueryHandler(af_ask_ids, pattern="^af_ev_\\d+$"))
    app.add_handler(CallbackQueryHandler(af_ask_purchase_ids, pattern="^af_purchase_\\d+$"))
    app.add_handler(CallbackQueryHandler(adj_game_select, pattern="^adj_game_\\d+$"))
    app.add_handler(CallbackQueryHandler(adj_ask_gps_adid, pattern="^adj_ev_\\d+$"))
    app.add_handler(CallbackQueryHandler(sg_game_select, pattern="^sg_game_\\d+$"))
    app.add_handler(CallbackQueryHandler(sg_ask_ids, pattern="^sg_ev_\\d+$"))
    app.add_handler(CallbackQueryHandler(farm_new, pattern="^farm_new$"))
    app.add_handler(CallbackQueryHandler(farm_select_platform, pattern="^farm_(af|adj|sg)$"))
    app.add_handler(CallbackQueryHandler(farm_game_selected, pattern="^farm_game_(af|adj|sg)_\\d+$"))

    print("=" * 60)
    print("AK Bot Started")
    print(f"Admin IDs: {ADMIN_IDS}")
    print("=" * 60)
    app.run_polling()


if __name__ == "__main__":
    main()
