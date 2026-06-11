#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "6075014046,5697155314,8114043468").split(",") if x.strip()]
SUPPORT_USER = os.getenv("SUPPORT_USER", "@abodnft")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Performance Settings
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "50"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))

# Platform Types
PLATFORM_ANDROID = "android"
PLATFORM_IOS = "ios"
