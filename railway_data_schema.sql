-- ═══════════════════════════════════════════════════════════════
--  Pivot SQLite → Railway MySQL 完整数据迁移
--  包含: CREATE TABLE + INDEXES + INSERT DATA
-- ═══════════════════════════════════════════════════════════════

SET FOREIGN_KEY_CHECKS = 0;

-- ┌─────────────────────────────────────────────────────────────┐
-- │  1. 创建表结构
-- └─────────────────────────────────────────────────────────────┘

CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(100) NOT NULL,
        name VARCHAR(100) NOT NULL,
        role VARCHAR(20) NOT NULL,
        sport VARCHAR(50),
        school VARCHAR(200),
        team_name VARCHAR(200),
        position VARCHAR(100),
        coach_role VARCHAR(100),
        height INT,
        weight INT,
        preferences VARCHAR(500) NOT NULL DEFAULT '{}',
        created_at VARCHAR(30) NOT NULL,
        updated_at VARCHAR(30) NOT NULL
    );

CREATE TABLE IF NOT EXISTS alert_rules (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(200) NOT NULL,
        level VARCHAR(20) NOT NULL,
        sport VARCHAR(50) NOT NULL DEFAULT '*',
        conditions VARCHAR(2000) NOT NULL DEFAULT '{}',
        is_active INT NOT NULL DEFAULT 1,
        created_at VARCHAR(30) NOT NULL,
        updated_at VARCHAR(30) NOT NULL
    );

CREATE TABLE IF NOT EXISTS messages (
        id INT PRIMARY KEY AUTO_INCREMENT,
        sender_id INT NOT NULL,
        recipient_id INT NOT NULL,
        subject VARCHAR(255),
        body TEXT NOT NULL,
        alert_level VARCHAR(50),
        alert_type VARCHAR(50),
        read_at VARCHAR(30),
        created_at VARCHAR(30) NOT NULL
    );

CREATE TABLE IF NOT EXISTS coach_athlete_links (
        id INT PRIMARY KEY AUTO_INCREMENT,
        coach_id INT NOT NULL,
        athlete_id INT NOT NULL,
        role VARCHAR(50) NOT NULL DEFAULT 'primary',
        created_at VARCHAR(30) NOT NULL,
        updated_at VARCHAR(30) NOT NULL,
        UNIQUE(coach_id, athlete_id)
    );

CREATE TABLE IF NOT EXISTS checkins (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        date VARCHAR(30) NOT NULL,
        mood INT NOT NULL,
        motivation INT NOT NULL,
        fatigue INT NOT NULL,
        challenge VARCHAR(100) NOT NULL DEFAULT 'none',
        journal VARCHAR(2000) NOT NULL DEFAULT '',
        created_at VARCHAR(30) NOT NULL,
        updated_at VARCHAR(30) NOT NULL,
        UNIQUE(user_id, date)
    );

CREATE TABLE IF NOT EXISTS health_metrics (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        date VARCHAR(30) NOT NULL,
        hrv REAL,
        rhr REAL,
        sleep_hours REAL,
        sleep_deep_pct REAL,
        sleep_rem_pct REAL,
        spo2 REAL,
        respiratory_rate REAL,
        skin_temp REAL,
        source VARCHAR(50) NOT NULL DEFAULT 'manual',
        created_at VARCHAR(30) NOT NULL,
        UNIQUE(user_id, date)
    );

CREATE TABLE IF NOT EXISTS training_metrics (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        date VARCHAR(30) NOT NULL,
        distance REAL,
        avg_split REAL,
        avg_spm REAL,
        max_hr REAL,
        avg_hr REAL,
        duration_minutes REAL,
        training_type VARCHAR(50),
        training_phase VARCHAR(50),
        intensity_score INT,
        volume_score INT,
        focus_area VARCHAR(100),
        coach_notes TEXT,
        planned_load INT,
        actual_load INT,
        created_at VARCHAR(30) NOT NULL,
        UNIQUE(user_id, date)
    );

CREATE TABLE IF NOT EXISTS alerts (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        level VARCHAR(20) NOT NULL,
        type VARCHAR(100) NOT NULL,
        message TEXT NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'active',
        rule_id INT,
        triggered_at VARCHAR(30) NOT NULL,
        resolved_at VARCHAR(30),
        created_at VARCHAR(30) NOT NULL,
        updated_at VARCHAR(30) NOT NULL
    );

-- ┌─────────────────────────────────────────────────────────────┐
-- │  2. 创建索引
-- └─────────────────────────────────────────────────────────────┘

CREATE INDEX idx_messages_recipient ON messages(recipient_id, created_at);
CREATE INDEX idx_messages_sender ON messages(sender_id, created_at);
CREATE INDEX idx_messages_conversation ON messages(sender_id, recipient_id, created_at);
CREATE INDEX idx_links_coach ON coach_athlete_links(coach_id);
CREATE INDEX idx_links_athlete ON coach_athlete_links(athlete_id);
CREATE INDEX idx_checkins_user_date ON checkins(user_id, date);
CREATE INDEX idx_health_user_date ON health_metrics(user_id, date);
CREATE INDEX idx_training_user_date ON training_metrics(user_id, date);
CREATE INDEX idx_alerts_user ON alerts(user_id, triggered_at);
CREATE INDEX idx_alerts_status ON alerts(status, triggered_at);

-- ┌─────────────────────────────────────────────────────────────┐
SET FOREIGN_KEY_CHECKS = 1;
