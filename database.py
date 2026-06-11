#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import threading
import time
from typing import Dict, Any, Optional, Tuple, List
from config import DATABASE_URL, DB_POOL_SIZE, CACHE_TTL

class DatabasePool:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.pool = None
        self._init_pool()

    def _init_pool(self):
        try:
            if DATABASE_URL:
                self.pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=DB_POOL_SIZE,
                    dsn=DATABASE_URL
                )
                print("✅ PostgreSQL Pool initialized")
            else:
                print("⚠️ No DATABASE_URL - using connection per request")
        except Exception as e:
            print(f"❌ Error initializing pool: {e}")
            self.pool = None

    def get_connection(self):
        if self.pool:
            return self.pool.getconn()
        elif DATABASE_URL:
            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        else:
            raise Exception("No DATABASE_URL configured")

    def return_connection(self, conn):
        if self.pool:
            self.pool.putconn(conn)
        else:
            conn.close()

db_pool = DatabasePool()

def get_db():
    return db_pool.get_connection()

def return_db(conn):
    db_pool.return_connection(conn)

# Cache system
cache: Dict[str, Tuple[Any, float]] = {}
cache_lock = threading.Lock()

def cache_get(key: str) -> Optional[Any]:
    with cache_lock:
        if key in cache:
            value, timestamp = cache[key]
            if time.time() - timestamp < CACHE_TTL:
                return value
            del cache[key]
    return None

def cache_set(key: str, value: Any, ttl: int = CACHE_TTL) -> None:
    with cache_lock:
        cache[key] = (value, time.time())

def cache_clear(pattern: str = None) -> None:
    with cache_lock:
        if pattern is None:
            cache.clear()
        else:
            keys = [k for k in cache if pattern in k]
            for k in keys:
                del cache[k]
