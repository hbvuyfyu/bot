-- AK Bot Database Schema for PostgreSQL (Neon)
-- Run this SQL to create all required tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==================== Users Table ====================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    name VARCHAR(255),
    last_use TIMESTAMP,
    banned INTEGER DEFAULT 0,
    admin INTEGER DEFAULT 0,
    allowed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_requests INTEGER DEFAULT 0
);

-- ==================== Allowed Users Table ====================
CREATE TABLE IF NOT EXISTS allowed_users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    name VARCHAR(255),
    added_by BIGINT,
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== User Platform Table ====================
CREATE TABLE IF NOT EXISTS user_platform (
    user_id BIGINT PRIMARY KEY,
    platform VARCHAR(50) DEFAULT 'android'
);

-- ==================== Games (AppsFlyer) ====================
CREATE TABLE IF NOT EXISTS games_af (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE,
    display_name VARCHAR(255),
    package VARCHAR(255),
    dev_key VARCHAR(255),
    emoji VARCHAR(10)
);

-- ==================== Games (Singular) ====================
CREATE TABLE IF NOT EXISTS games_singular (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE,
    display_name VARCHAR(255),
    package VARCHAR(255),
    app_key VARCHAR(255),
    emoji VARCHAR(10)
);

-- ==================== Games (Adjust) ====================
CREATE TABLE IF NOT EXISTS games_adj (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE,
    display_name VARCHAR(255),
    app_token VARCHAR(255),
    emoji VARCHAR(10)
);

-- ==================== Events (AppsFlyer) ====================
CREATE TABLE IF NOT EXISTS events_af (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games_af(id) ON DELETE CASCADE,
    event_name VARCHAR(255),
    display_name VARCHAR(255),
    event_type VARCHAR(100),
    is_purchase INTEGER DEFAULT 0
);

-- ==================== Events (Singular) ====================
CREATE TABLE IF NOT EXISTS events_singular (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games_singular(id) ON DELETE CASCADE,
    event_name VARCHAR(255),
    display_name VARCHAR(255),
    event_type VARCHAR(100)
);

-- ==================== Events (Adjust) ====================
CREATE TABLE IF NOT EXISTS events_adj (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games_adj(id) ON DELETE CASCADE,
    event_name VARCHAR(255),
    event_token VARCHAR(255),
    display_name VARCHAR(255),
    level_value INTEGER DEFAULT 0
);

-- ==================== Proxies Table ====================
CREATE TABLE IF NOT EXISTS proxies (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE,
    proxy_type VARCHAR(50),
    proxy_host VARCHAR(255),
    proxy_port INTEGER,
    proxy_user VARCHAR(255),
    proxy_pass VARCHAR(255),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    usage_count INTEGER DEFAULT 0
);

-- ==================== Farm Tasks Table ====================
CREATE TABLE IF NOT EXISTS farm_tasks (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    task_name VARCHAR(255) UNIQUE,
    platform VARCHAR(50),
    game_id INTEGER,
    game_name VARCHAR(255),
    start_level INTEGER,
    end_level INTEGER,
    total_days INTEGER,
    mode VARCHAR(50),
    current_day INTEGER,
    current_level INTEGER,
    status VARCHAR(50),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_run TIMESTAMP,
    aifa TEXT,
    gaid TEXT,
    uid TEXT,
    af_uid TEXT,
    gps_adid TEXT,
    idfa TEXT,
    idfv TEXT,
    att_status INTEGER,
    completed_levels INTEGER DEFAULT 0,
    failed_attempts INTEGER DEFAULT 0
);

-- ==================== User Stats Table ====================
CREATE TABLE IF NOT EXISTS user_stats (
    user_id BIGINT PRIMARY KEY,
    last_daily_reset TIMESTAMP,
    daily_requests INTEGER DEFAULT 0,
    total_af_requests INTEGER DEFAULT 0,
    total_adj_requests INTEGER DEFAULT 0,
    total_singular_requests INTEGER DEFAULT 0
);

-- ==================== Indexes ====================
CREATE INDEX IF NOT EXISTS idx_users_allowed ON users(allowed);
CREATE INDEX IF NOT EXISTS idx_users_banned ON users(banned);
CREATE INDEX IF NOT EXISTS idx_farm_tasks_user ON farm_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_farm_tasks_status ON farm_tasks(status);
CREATE INDEX IF NOT EXISTS idx_events_af_game ON events_af(game_id);
CREATE INDEX IF NOT EXISTS idx_events_adj_game ON events_adj(game_id);
CREATE INDEX IF NOT EXISTS idx_events_singular_game ON events_singular(game_id);
CREATE INDEX IF NOT EXISTS idx_proxies_user ON proxies(user_id);
CREATE INDEX IF NOT EXISTS idx_user_platform ON user_platform(user_id);

-- ==================== Admin Users (Insert Default Admins) ====================
INSERT INTO users (user_id, username, name, admin, allowed, created_at)
VALUES
    (6075014046, 'admin', 'Admin', 1, 1, CURRENT_TIMESTAMP),
    (8114043468, 'admin2', 'Admin2', 1, 1, CURRENT_TIMESTAMP)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO allowed_users (user_id, username, name, added_by, added_date)
VALUES
    (6075014046, 'admin', 'Admin', 6075014046, CURRENT_TIMESTAMP),
    (8114043468, 'admin2', 'Admin2', 6075014046, CURRENT_TIMESTAMP)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_platform (user_id, platform)
VALUES
    (6075014046, 'android'),
    (8114043468, 'android')
ON CONFLICT (user_id) DO NOTHING;

-- ==================== Sample Games Data (AppsFlyer) ====================
INSERT INTO games_af (name, display_name, package, dev_key, emoji) VALUES
    ('dice_dream', 'Dice Dreams', 'com.superplaystudios.dicedreams', 'Hn5qYjVAaRNJYDcwF4LaWF', '🎲'),
    ('domino_dreams', 'Domino Dreams', 'com.screenshake.dominodreams', 'Hn5qYjVAaRNJYDcwF4LaWF', '🃏'),
    ('coin_master', 'Coin Master', 'com.moonactive.coinmaster', 'H3KjoCRVTiVgA5mWSAHtCe', '🎲'),
    ('royal_match', 'Royal Match', 'com.dreamgames.royalmatch', 'B27HnbGEcbWC2fv79DDhcb', '👑'),
    ('merge_gardens', 'Merge Gardens', 'com.futureplay.mergematch', 'nr8SibwpFjcKGBQNpDdttd', '🌺'),
    ('zombie_waves', 'Zombie Waves', 'com.ddup.zombiewaves.zw', 'wiQMRPvGaAYTGBCgM5yN9N', '🧟')
ON CONFLICT (name) DO NOTHING;

-- ==================== Sample Games Data (Adjust) ====================
INSERT INTO games_adj (name, display_name, app_token, emoji) VALUES
    ('get_color', 'Get Color', '367kicwptj5s', '🎨'),
    ('merge_blocks', '2048 X2 Merge Blocks', '367kicwptj5s', '🔲'),
    ('puzzle2248', '2248 Puzzle', '367kicwptj5s', '🧩'),
    ('alice_blastland', 'Alice in Blastland', '367kicwptj5s', '🌸'),
    ('army_tycoon', 'Army Tycoon', '367kicwptj5s', '🎖️'),
    ('battle_night', 'Battle Night', '367kicwptj5s', '⚔️')
ON CONFLICT (name) DO NOTHING;

-- ==================== Sample Games Data (Singular) ====================
INSERT INTO games_singular (name, display_name, package, app_key, emoji) VALUES
    ('animals_coins', 'Animals & Coins', 'com.innplaylabs.animalkingdomraid', 'innplay_labs_33d87c9b', '🦁'),
    ('time_master', 'Time Master', 'com.firefog.timemaster', 'myappfree_spa_38e49215', '⏰'),
    ('beast_go', 'Beast Go', 'com.ninthart.board.beastgo', 'myappfree_spa_38e49215', '🐉'),
    ('pop_slots', 'POP Slots', 'com.playstudios.popslots', 'playstudios_3852f898', '🎰'),
    ('mgm_slots', 'MGM Slots Live', 'com.playstudios.showstar', 'playstudios_3852f898', '🎰'),
    ('eatventure', 'Eatventure', 'com.hwqgrhhjfd.idlefastfood', 'lessmore_edff53fc', '🍔')
ON CONFLICT (name) DO NOTHING;

-- ==================== Row Level Security (Optional) ====================
-- Enable RLS if you want row-level security
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE farm_tasks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE proxies ENABLE ROW LEVEL SECURITY;

-- ==================== Completion Message ====================
SELECT '✅ Database schema created successfully!' as status;
