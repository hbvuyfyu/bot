#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from database import get_db, return_db, cache_get, cache_set, cache_clear
from datetime import datetime
from config import ADMIN_IDS, CACHE_TTL
from functools import lru_cache

# ==================== Helper Functions ====================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@lru_cache(maxsize=10000)
def is_allowed_cached(user_id: int) -> bool:
    if is_admin(user_id):
        return True
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM allowed_users WHERE user_id = %s", (user_id,))
            return cur.fetchone() is not None
    finally:
        return_db(conn)

def is_allowed(user_id: int) -> bool:
    return is_allowed_cached(user_id)

# ==================== User Management ====================

def get_user_platform(user_id: int) -> str:
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT platform FROM user_platform WHERE user_id = %s", (user_id,))
            result = cur.fetchone()
            if result:
                return result['platform']
            cur.execute("INSERT INTO user_platform (user_id, platform) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user_id, "android"))
            conn.commit()
            return "android"
    finally:
        return_db(conn)

def set_user_platform(user_id: int, platform: str) -> None:
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO user_platform (user_id, platform) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET platform = %s", (user_id, platform, platform))
            conn.commit()
    finally:
        return_db(conn)

def add_allowed_user(user_id: int, username: str, name: str, admin_id: int) -> None:
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO allowed_users (user_id, username, name, added_by, added_date) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id) DO NOTHING", (user_id, username, name, admin_id, datetime.now()))
            cur.execute("UPDATE users SET allowed = 1 WHERE user_id = %s", (user_id,))
            conn.commit()
            is_allowed_cached.cache_clear()
    finally:
        return_db(conn)

def remove_allowed_user(user_id: int) -> None:
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM allowed_users WHERE user_id = %s", (user_id,))
            cur.execute("UPDATE users SET allowed = 0 WHERE user_id = %s", (user_id,))
            conn.commit()
            is_allowed_cached.cache_clear()
    finally:
        return_db(conn)

def get_allowed_users():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, username, name, added_date FROM allowed_users")
            return cur.fetchall()
    finally:
        return_db(conn)

def increment_user_requests(user_id: int) -> None:
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET total_requests = total_requests + 1, last_use = %s WHERE user_id = %s", (datetime.now(), user_id))
            conn.commit()
    finally:
        return_db(conn)

# ==================== Games ====================

def get_all_games_af():
    cached = cache_get("games_af")
    if cached:
        return cached
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, display_name, package, dev_key, emoji FROM games_af")
            games = cur.fetchall()
            cache_set("games_af", games)
            return games
    finally:
        return_db(conn)

def get_all_games_singular():
    cached = cache_get("games_singular")
    if cached:
        return cached
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, display_name, package, app_key, emoji FROM games_singular")
            games = cur.fetchall()
            cache_set("games_singular", games)
            return games
    finally:
        return_db(conn)

def get_all_games_adj():
    cached = cache_get("games_adj")
    if cached:
        return cached
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, display_name, app_token, emoji FROM games_adj")
            games = cur.fetchall()
            cache_set("games_adj", games)
            return games
    finally:
        return_db(conn)

# ==================== Events ====================

def get_af_events(game_id: int, purchase_only: bool = False):
    key = f"af_events_{game_id}_{purchase_only}"
    cached = cache_get(key)
    if cached:
        return cached
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if purchase_only:
                cur.execute("SELECT id, event_name, display_name FROM events_af WHERE game_id = %s AND is_purchase = 1", (game_id,))
            else:
                cur.execute("SELECT id, event_name, display_name FROM events_af WHERE game_id = %s AND is_purchase = 0", (game_id,))
            events = cur.fetchall()
            cache_set(key, events)
            return events
    finally:
        return_db(conn)

def get_singular_events(game_id: int):
    key = f"singular_events_{game_id}"
    cached = cache_get(key)
    if cached:
        return cached
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, event_name, display_name FROM events_singular WHERE game_id = %s", (game_id,))
            events = cur.fetchall()
            cache_set(key, events)
            return events
    finally:
        return_db(conn)

def get_adj_events(game_id: int):
    key = f"adj_events_{game_id}"
    cached = cache_get(key)
    if cached:
        return cached
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, event_name, event_token, display_name, level_value FROM events_adj WHERE game_id = %s ORDER BY level_value", (game_id,))
            events = cur.fetchall()
            cache_set(key, events)
            return events
    finally:
        return_db(conn)

# ==================== Proxy Management ====================

def save_proxy(user_id: int, proxy_type: str, proxy_host: str, proxy_port: int, proxy_user: str, proxy_pass: str):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO proxies (user_id, proxy_type, proxy_host, proxy_port, proxy_user, proxy_pass, created_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    proxy_type = %s, proxy_host = %s, proxy_port = %s, proxy_user = %s, proxy_pass = %s
            """, (user_id, proxy_type, proxy_host, proxy_port, proxy_user, proxy_pass, datetime.now(),
                  proxy_type, proxy_host, proxy_port, proxy_user, proxy_pass))
            conn.commit()
    finally:
        return_db(conn)

def delete_proxy(user_id: int):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM proxies WHERE user_id = %s", (user_id,))
            conn.commit()
    finally:
        return_db(conn)

def get_proxy_info(user_id: int):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT proxy_type, proxy_host, proxy_port, proxy_user, proxy_pass FROM proxies WHERE user_id = %s", (user_id,))
            return cur.fetchone()
    finally:
        return_db(conn)

def get_proxy_for_user(user_id: int) -> dict:
    proxy_info = get_proxy_info(user_id)
    if not proxy_info:
        return None
    proxy_type = proxy_info['proxy_type']
    proxy_host = proxy_info['proxy_host']
    proxy_port = proxy_info['proxy_port']
    proxy_user = proxy_info['proxy_user']
    proxy_pass = proxy_info['proxy_pass']
    proxies = {}
    if proxy_type in ("http", "https"):
        auth = f"{proxy_user}:{proxy_pass}@" if proxy_user and proxy_pass else ""
        proxies[proxy_type] = f"{proxy_type}://{auth}{proxy_host}:{proxy_port}"
    elif proxy_type == "socks5":
        auth = f"{proxy_user}:{proxy_pass}@" if proxy_user and proxy_pass else ""
        proxies["socks5"] = f"socks5://{auth}{proxy_host}:{proxy_port}"
    return proxies
