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
-- │  3. 导入数据
-- └─────────────────────────────────────────────────────────────┘

-- users: 13 行
DELETE FROM users;
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (1, '2', '$2b$12$GjPI0EyAi7zMAqPRNlkXgO4e7n4f1ReUg2i0omEeokuVJvVaT3PFq', 'Test Athlete 2', 'athlete', 'rowing', 'University of Pennsylvania', 'Test Team', 'Stroke Seat', NULL, 188, 82, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:17.414832', '2026-08-05T01:33:17.414832');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (2, 'assistant@pivot.dev', '$2b$12$yVbAGfYJM5TzWDUJLBZyUe09qS8F6LSPayHa40wcmhDvO80hco/lO', 'Assistant Coach', 'coach', 'rowing', 'Test University', 'Test Rowing', NULL, 'Assistant Coach', NULL, NULL, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:18.703669', '2026-08-05T01:33:18.703669');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (3, 'head@pivot.dev', '$2b$12$iGEB26bNJahPyNQIM/pwwezO7kk2w7P1w9K0SORRhljn6Atdor9ae', 'Head Coach', 'coach', 'rowing', 'Test University', 'Test Rowing', NULL, 'Head Coach', NULL, NULL, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:19.294598', '2026-08-05T01:33:19.294598');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (4, 'strength@pivot.dev', '$2b$12$j6Jb1LRrADX/BU2QJNja4.JOui1ruww3iq/HYK910H.ZlNUilSBiu', 'Strength Coach', 'coach', 'rowing', 'Test University', 'Test Rowing', NULL, 'Strength & Conditioning Coach', NULL, NULL, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:20.264235', '2026-08-05T01:33:20.264235');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (5, 'psych@pivot.dev', '$2b$12$Gicz.CUvH8hZGcu7t/lTduBu1/rlRXbdg3IfpaTmAY/VzEBn.5p3K', 'Sports Psych', 'coach', 'rowing', 'Test University', 'Test Rowing', NULL, 'Sports Psychologist', NULL, NULL, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:20.728201', '2026-08-05T01:33:20.728201');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (6, 'trainer@pivot.dev', '$2b$12$p3fneQ.BLAB9siRO59VijObBiwb9NhrSvoZNRi55AJeRr1cXCsibe', 'Athletic Trainer', 'coach', 'rowing', 'Test University', 'Test Rowing', NULL, 'Athletic Trainer', NULL, NULL, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:21.298689', '2026-08-05T01:33:21.298689');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (7, 'analyst@pivot.dev', '$2b$12$wZ464E.IURm3EOoD6xQtMO22p5WdAH1o9EqHtV0ORAufEEBa1LVV.', 'Performance Analyst', 'coach', 'rowing', 'Test University', 'Test Rowing', NULL, 'Performance Analyst', NULL, NULL, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:21.933028', '2026-08-05T01:33:21.933028');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (8, 'alex.chen@pivot.dev', '$2b$12$fa4pSD.zxe9fzcz1rf5n..1vk6r.chBl3LdnRKeMwE1dmNX4rCw42', 'Alex Chen', 'athlete', 'rowing', 'University of Pennsylvania', 'Varsity Heavyweight 8+', 'Stroke Seat', NULL, 191, 86, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:40.480911', '2026-08-05T01:33:40.480911');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (9, 'jordan.lee@pivot.dev', '$2b$12$mBvbo2XMLhVjsSInQzO9EO1L/SQsqKXJuJ.cCOpxFkCG20pCINgJi', 'Jordan Lee', 'athlete', 'rowing', 'University of Pennsylvania', 'Varsity Heavyweight 8+', 'Bow Seat', NULL, 188, 82, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:41.182056', '2026-08-05T01:33:41.182056');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (10, 'morgan.smith@pivot.dev', '$2b$12$t0x5NCKVkmSJ2a3B62vi9uFuYi8w4p10bQw5qmR3V8NN1FQedIMZi', 'Morgan Smith', 'athlete', 'rowing', 'University of Pennsylvania', 'Varsity Heavyweight 8+', '3 Seat', NULL, 196, 89, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:42.154311', '2026-08-05T01:33:42.154311');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (11, 'casey.park@pivot.dev', '$2b$12$b5yIxnlRCZnEvneDlfSf3OSK6WMx8SnkOOnuwmk1HvUhjLLsumyWm', 'Casey Park', 'athlete', 'rowing', 'University of Pennsylvania', 'Varsity Heavyweight 8+', 'Coxswain', NULL, 165, 55, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:43.209916', '2026-08-05T01:33:43.209916');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (12, 'riley.kim@pivot.dev', '$2b$12$Zx4UqwTsE6X22S5n6.yQ7ONdj88o5W/XjF20OyH71PVuPhC.NVC1S', 'Riley Kim', 'athlete', 'rowing', 'University of Washington', 'Varsity 8+', '2 Seat', NULL, 193, 88, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:44.326743', '2026-08-05T01:33:44.326743');
INSERT INTO users (id, email, password_hash, name, role, sport, school, team_name, position, coach_role, height, weight, preferences, created_at, updated_at) VALUES (13, 'taylor.brooks@pivot.dev', '$2b$12$rRhevJNaE25uyCkc34RaLO1dt23Pte.8TimRqS0tGy9GN91uYKv42', 'Taylor Brooks', 'athlete', 'rowing', 'University of Washington', 'Varsity 8+', '4 Seat', NULL, 190, 84, '{"alertNotifications": true, "weeklyReport": true}', '2026-08-05T01:33:45.562274', '2026-08-05T01:33:45.562274');

-- alert_rules: 6 行
DELETE FROM alert_rules;
INSERT INTO alert_rules (id, name, level, sport, conditions, is_active, created_at, updated_at) VALUES (1, 'Recovery Deficiency', 'yellow', 'rowing', '{"type": "trend", "message": "HRV declined over recent check-ins \u2014 prioritize active recovery today."}', 1, '2026-08-05T01:33:39.923953', '2026-08-05T01:33:39.923953');
INSERT INTO alert_rules (id, name, level, sport, conditions, is_active, created_at, updated_at) VALUES (2, 'Sleep Deprivation', 'yellow', 'rowing', '{"metric": "sleep_hours", "operator": "<", "threshold": 6, "message": "Reported sleep under 6 hours \u2014 emotional vulnerability risk."}', 1, '2026-08-05T01:33:39.926169', '2026-08-05T01:33:39.926169');
INSERT INTO alert_rules (id, name, level, sport, conditions, is_active, created_at, updated_at) VALUES (3, 'Physical & Mental Fatigue', 'red', 'rowing', '{"metric": "hrv", "operator": "<", "threshold": 45, "message": "HRV critically low \u2014 burnout risk."}', 1, '2026-08-05T01:33:39.927788', '2026-08-05T01:33:39.927788');
INSERT INTO alert_rules (id, name, level, sport, conditions, is_active, created_at, updated_at) VALUES (4, 'Sleep Deprivation — Critical', 'red', 'rowing', '{"metric": "sleep_hours", "operator": "<", "threshold": 5, "message": "3+ nights poor sleep \u2014 consider reducing load."}', 1, '2026-08-05T01:33:39.929284', '2026-08-05T01:33:39.929284');
INSERT INTO alert_rules (id, name, level, sport, conditions, is_active, created_at, updated_at) VALUES (5, 'Mood Decline', 'red', '*', '{"checkin": "mood", "operator": "<", "threshold": 2, "message": "Mood score dropped significantly \u2014 check in personally."}', 1, '2026-08-05T01:33:39.930585', '2026-08-05T01:33:39.930585');
INSERT INTO alert_rules (id, name, level, sport, conditions, is_active, created_at, updated_at) VALUES (6, 'URGENT: Athlete in Crisis', 'black', 'rowing', '{"metric": "hrv", "operator": "<", "threshold": 35, "message": "Multiple severe markers \u2014 immediate coach intervention needed."}', 1, '2026-08-05T01:33:39.931961', '2026-08-05T01:33:39.931961');

-- messages: 35 行
DELETE FROM messages;
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (1, 5, 2, NULL, 'Hi tim, I noticed your HRV dropped 12% this week. How are you feeling?', NULL, NULL, NULL, '2026-08-05T01:33:50.898475');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (2, 2, 5, NULL, 'Hey coach. Yeah I''ve been sleeping poorly — exams coming up. Pushing through.', NULL, NULL, NULL, '2026-08-05T01:33:50.900344');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (3, 5, 2, NULL, 'Understood. Let''s reduce Thursday''s erg session from 18k to 12k. Recovery first.', NULL, NULL, NULL, '2026-08-05T01:33:50.902197');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (4, 2, 5, NULL, 'Thanks, that helps. I''ll make sure to get 8 hours tonight.', NULL, NULL, NULL, '2026-08-05T01:33:50.903877');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (5, 5, 2, NULL, 'Great. Also, the team nutritionist suggested more carbs before AM practice. Try it.', NULL, NULL, NULL, '2026-08-05T01:33:50.905332');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (6, 2, 5, NULL, 'Will do. Toast before 6am rowing it is 🍞', NULL, NULL, NULL, '2026-08-05T01:33:50.906641');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (7, 5, 2, NULL, 'Haha exactly. I''ll check your numbers Friday.', NULL, NULL, NULL, '2026-08-05T01:33:50.907963');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (8, 8, 1, '⚠️ Elevated Resting HR Alert', 'Morgan, your resting HR has been trending up for 3 days (62→71 bpm). Any illness or unusual stress?', 'warning', 'Heart Rate', NULL, '2026-08-05T01:33:50.910563');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (9, 1, 8, NULL, 'Nothing major — just some midterm stress. But I''ll keep an eye on it.', NULL, NULL, NULL, '2026-08-05T01:33:50.912935');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (10, 8, 1, NULL, 'Ok. Let''s flag it. Take tomorrow off from erg work. Light stretch only.', NULL, NULL, NULL, '2026-08-05T01:33:50.914486');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (11, 1, 8, NULL, 'Got it. I''ll rest and hydrate.', NULL, NULL, NULL, '2026-08-05T01:33:50.916432');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (12, 7, 4, NULL, 'Hey Sarah, just checking in. Your 2k split has improved 3 seconds since last month. Nice work!', NULL, NULL, NULL, '2026-08-05T01:33:50.918828');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (13, 4, 7, NULL, 'Thank you! I''ve been adding morning yoga — seems to help my flexibility.', NULL, NULL, NULL, '2026-08-05T01:33:50.920055');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (14, 7, 4, NULL, 'The data shows it. Keep it up. Don''t forget: hydration goal is 3L on heavy training days.', NULL, NULL, NULL, '2026-08-05T01:33:50.921312');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (15, 4, 7, NULL, 'Noted! I''ll set a reminder on my phone.', NULL, NULL, NULL, '2026-08-05T01:33:50.922535');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (16, 5, 3, '🔴 URGENT: Sleep Deficiency Critical', 'URGENT: Your sleep score has been under 40 for 4 consecutive nights. This is a red alert.', 'critical', 'Sleep', NULL, '2026-08-05T01:33:50.925083');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (17, 2, 5, NULL, '(This is tim''s coach responding) I''ll make sure he sees this today.', NULL, NULL, NULL, '2026-08-05T01:33:50.926474');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (18, 3, 5, NULL, 'Sorry coach. Been gaming late. I''ll cut it off by 10pm from now on.', NULL, NULL, NULL, '2026-08-05T01:33:50.927729');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (19, 5, 3, NULL, 'Appreciate the honesty. We''ll re-evaluate your sleep data next Monday. Zero screens after 10pm.', NULL, NULL, NULL, '2026-08-05T01:33:50.929094');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (20, 8, 7, 'URGENT: Morgan Smith — Crisis Alert', 'FYI: Morgan (Test User) showed BLACK alert today — heart rate + sleep both critical. All coaches stay aware.', 'black', 'Multi-System Crisis', NULL, '2026-08-05T01:33:50.930709');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (21, 7, 8, NULL, 'On it. I''ll pull her training log and review recent workloads.', NULL, NULL, NULL, '2026-08-05T01:33:50.932134');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (22, 8, 7, NULL, 'Good. Strength coach also notified. Let''s meet after practice tomorrow.', NULL, NULL, NULL, '2026-08-05T01:33:50.933521');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (23, 8, 9, '⚠️ Morgan Smith — Modify Strength Plan', 'Morgan''s data is critical — may need to modify her strength plan this week. Can you review?', 'black', 'Multi-System Crisis', NULL, '2026-08-05T01:33:50.935099');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (24, 9, 8, NULL, 'Agreed. I''ll drop her squat volume by 30% and add mobility work instead.', NULL, NULL, NULL, '2026-08-05T01:33:50.936913');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (25, 10, 1, NULL, 'Hi Morgan. Your team mentioned you might benefit from a mental skills session. Want to chat?', NULL, NULL, NULL, '2026-08-05T01:33:50.938490');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (26, 1, 10, NULL, 'That would be great. Pre-race anxiety has been rough lately.', NULL, NULL, NULL, '2026-08-05T01:33:50.939992');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (27, 10, 1, NULL, 'Let''s schedule 20min this Friday. I''ll send you a breathing exercise to try before then.', NULL, NULL, NULL, '2026-08-05T01:33:50.942257');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (28, 9, 2, NULL, 'Tim, your squat progression is solid. Add 5kg next week and keep the 3x5 rep scheme.', NULL, NULL, NULL, '2026-08-05T01:33:50.944515');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (29, 2, 9, NULL, 'Copy that. Should I keep the accessory work the same?', NULL, NULL, NULL, '2026-08-05T01:33:50.947763');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (30, 9, 2, NULL, 'Yes — lunges and core stability stay. Drop the plyos this week for recovery.', NULL, NULL, NULL, '2026-08-05T01:33:50.949559');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (31, 12, 8, '📊 Weekly Performance Metrics', 'Weekly performance review: Sarah +3%, Tim -2%, Morgan -8% (but flagged for recovery). Full report attached.', 'info', 'Performance', NULL, '2026-08-05T01:33:50.951428');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (32, 8, 12, NULL, 'Thanks. Morgan''s -8% aligns with what we''re seeing. Let''s revisit after her recovery week.', NULL, NULL, NULL, '2026-08-05T01:33:50.952943');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (33, 11, 4, NULL, 'Sarah, you reported left shoulder tightness after yesterday''s session. Still sore today?', NULL, NULL, NULL, '2026-08-05T01:33:50.954952');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (34, 4, 11, NULL, 'A bit better. I did the mobility routine you gave me. Think I can erg today?', NULL, NULL, NULL, '2026-08-05T01:33:50.956287');
INSERT INTO messages (id, sender_id, recipient_id, subject, body, alert_level, alert_type, read_at, created_at) VALUES (35, 11, 4, NULL, 'Yes, but at 70% effort. Stop immediately if you feel sharp pain. I''ll check on you during practice.', NULL, NULL, NULL, '2026-08-05T01:33:50.957523');

-- coach_athlete_links: 6 行
DELETE FROM coach_athlete_links;
INSERT INTO coach_athlete_links (id, coach_id, athlete_id, role, created_at, updated_at) VALUES (1, 3, 8, 'primary', '2026-08-05T01:33:40.484989', '2026-08-05T01:33:40.484989');
INSERT INTO coach_athlete_links (id, coach_id, athlete_id, role, created_at, updated_at) VALUES (2, 3, 9, 'primary', '2026-08-05T01:33:41.189021', '2026-08-05T01:33:41.189021');
INSERT INTO coach_athlete_links (id, coach_id, athlete_id, role, created_at, updated_at) VALUES (3, 3, 10, 'primary', '2026-08-05T01:33:42.163371', '2026-08-05T01:33:42.163371');
INSERT INTO coach_athlete_links (id, coach_id, athlete_id, role, created_at, updated_at) VALUES (4, 3, 11, 'primary', '2026-08-05T01:33:43.214666', '2026-08-05T01:33:43.214666');
INSERT INTO coach_athlete_links (id, coach_id, athlete_id, role, created_at, updated_at) VALUES (5, 3, 12, 'primary', '2026-08-05T01:33:44.337945', '2026-08-05T01:33:44.337945');
INSERT INTO coach_athlete_links (id, coach_id, athlete_id, role, created_at, updated_at) VALUES (6, 3, 13, 'primary', '2026-08-05T01:33:45.569354', '2026-08-05T01:33:45.569354');

-- checkins: 42 行
DELETE FROM checkins;
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (1, 8, '2026-07-10', 4, 8, 4, 'none', 'Feeling strong today, ready to train', '2026-08-05T01:33:40.530129', '2026-08-05T01:33:40.530129');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (2, 8, '2026-07-11', 4, 7, 5, 'physical_fatigue', '', '2026-08-05T01:33:40.533504', '2026-08-05T01:33:40.533504');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (3, 8, '2026-07-12', 5, 8, 3, 'none', 'Great sleep last night', '2026-08-05T01:33:40.536440', '2026-08-05T01:33:40.536440');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (4, 8, '2026-07-13', 4, 7, 4, 'none', '', '2026-08-05T01:33:40.539145', '2026-08-05T01:33:40.539145');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (5, 8, '2026-07-14', 3, 6, 6, 'physical_fatigue', 'Tired but pushing through', '2026-08-05T01:33:40.542109', '2026-08-05T01:33:40.542109');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (6, 8, '2026-07-15', 4, 7, 5, 'none', '', '2026-08-05T01:33:40.545299', '2026-08-05T01:33:40.545299');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (7, 8, '2026-07-16', 4, 8, 4, 'none', 'Feeling strong today, ready to train', '2026-08-05T01:33:40.547977', '2026-08-05T01:33:40.547977');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (8, 9, '2026-07-10', 4, 7, 4, 'physical_fatigue', 'Okay today', '2026-08-05T01:33:41.266572', '2026-08-05T01:33:41.266572');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (9, 9, '2026-07-11', 4, 6, 5, 'physical_fatigue', 'Tired but pushing through', '2026-08-05T01:33:41.270460', '2026-08-05T01:33:41.270460');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (10, 9, '2026-07-12', 3, 5, 6, 'mental_fatigue', 'Tired but pushing through', '2026-08-05T01:33:41.276670', '2026-08-05T01:33:41.276670');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (11, 9, '2026-07-13', 3, 5, 6, 'mental_fatigue', 'Everything feels heavy. Not sure I want to keep going.', '2026-08-05T01:33:41.281147', '2026-08-05T01:33:41.281147');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (12, 9, '2026-07-14', 2, 4, 7, 'mental_fatigue', 'Everything feels heavy. Not sure I want to keep going.', '2026-08-05T01:33:41.287647', '2026-08-05T01:33:41.287647');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (13, 9, '2026-07-15', 2, 3, 8, 'mental_fatigue', 'Everything feels heavy. Not sure I want to keep going.', '2026-08-05T01:33:41.292358', '2026-08-05T01:33:41.292358');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (14, 9, '2026-07-16', 2, 3, 8, 'mental_fatigue', 'Everything feels heavy. Not sure I want to keep going.', '2026-08-05T01:33:41.295740', '2026-08-05T01:33:41.295740');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (15, 10, '2026-07-10', 3, 5, 5, 'physical_fatigue', 'Struggling to keep pace, everything hurts', '2026-08-05T01:33:42.231706', '2026-08-05T01:33:42.231706');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (16, 10, '2026-07-11', 3, 4, 6, 'physical_fatigue', 'Struggling to keep pace, everything hurts', '2026-08-05T01:33:42.235612', '2026-08-05T01:33:42.235612');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (17, 10, '2026-07-12', 2, 3, 7, 'mental_fatigue', 'Struggling to keep pace, everything hurts', '2026-08-05T01:33:42.238737', '2026-08-05T01:33:42.238737');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (18, 10, '2026-07-13', 2, 2, 8, 'mental_fatigue', 'Can''t do this anymore. Body won''t cooperate. Mind is blank.', '2026-08-05T01:33:42.242548', '2026-08-05T01:33:42.242548');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (19, 10, '2026-07-14', 1, 1, 9, 'mental_fatigue', 'Can''t do this anymore. Body won''t cooperate. Mind is blank.', '2026-08-05T01:33:42.248701', '2026-08-05T01:33:42.248701');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (20, 10, '2026-07-15', 1, 1, 9, 'mental_fatigue', 'Can''t do this anymore. Body won''t cooperate. Mind is blank.', '2026-08-05T01:33:42.252389', '2026-08-05T01:33:42.252389');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (21, 10, '2026-07-16', 1, 1, 9, 'mental_fatigue', 'Can''t do this anymore. Body won''t cooperate. Mind is blank.', '2026-08-05T01:33:42.256013', '2026-08-05T01:33:42.256013');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (22, 11, '2026-07-10', 2, 4, 6, 'physical_fatigue', 'Barely holding on. Don''t know how much longer.', '2026-08-05T01:33:43.288018', '2026-08-05T01:33:43.288018');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (23, 11, '2026-07-11', 2, 3, 7, 'physical_fatigue', 'Barely holding on. Don''t know how much longer.', '2026-08-05T01:33:43.292894', '2026-08-05T01:33:43.292894');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (24, 11, '2026-07-12', 2, 2, 8, 'mental_fatigue', 'Barely holding on. Don''t know how much longer.', '2026-08-05T01:33:43.295745', '2026-08-05T01:33:43.295745');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (25, 11, '2026-07-13', 1, 2, 8, 'mental_fatigue', 'Barely holding on. Don''t know how much longer.', '2026-08-05T01:33:43.303251', '2026-08-05T01:33:43.303251');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (26, 11, '2026-07-14', 1, 1, 9, 'mental_fatigue', 'I feel invisible. Nobody notices I''m drowning.', '2026-08-05T01:33:43.306528', '2026-08-05T01:33:43.306528');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (27, 11, '2026-07-15', 1, 1, 9, 'mental_fatigue', 'I feel invisible. Nobody notices I''m drowning.', '2026-08-05T01:33:43.310906', '2026-08-05T01:33:43.310906');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (28, 11, '2026-07-16', 1, 1, 9, 'mental_fatigue', 'I feel invisible. Nobody notices I''m drowning.', '2026-08-05T01:33:43.314871', '2026-08-05T01:33:43.314871');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (29, 12, '2026-07-10', 5, 9, 3, 'none', 'Feeling strong today, ready to train', '2026-08-05T01:33:44.867731', '2026-08-05T01:33:44.867731');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (30, 12, '2026-07-11', 4, 8, 3, 'none', 'Feeling strong today, ready to train', '2026-08-05T01:33:44.872012', '2026-08-05T01:33:44.872012');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (31, 12, '2026-07-12', 5, 9, 2, 'none', 'Feeling strong today, ready to train', '2026-08-05T01:33:44.893171', '2026-08-05T01:33:44.893171');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (32, 12, '2026-07-13', 4, 8, 3, 'none', 'Feeling strong today, ready to train', '2026-08-05T01:33:44.898490', '2026-08-05T01:33:44.898490');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (33, 12, '2026-07-14', 5, 9, 2, 'none', 'Feeling strong today, ready to train', '2026-08-05T01:33:44.908406', '2026-08-05T01:33:44.908406');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (34, 12, '2026-07-15', 4, 7, 4, 'none', 'Feeling strong today, ready to train', '2026-08-05T01:33:44.913891', '2026-08-05T01:33:44.913891');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (35, 12, '2026-07-16', 5, 9, 3, 'none', 'Feeling strong today, ready to train', '2026-08-05T01:33:44.917489', '2026-08-05T01:33:44.917489');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (36, 13, '2026-07-10', 3, 5, 7, 'mental_fatigue', 'Coming back slowly, feeling better each day', '2026-08-05T01:33:45.699140', '2026-08-05T01:33:45.699140');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (37, 13, '2026-07-11', 3, 6, 6, 'mental_fatigue', 'Coming back slowly, feeling better each day', '2026-08-05T01:33:45.704653', '2026-08-05T01:33:45.704653');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (38, 13, '2026-07-12', 4, 7, 5, 'none', 'Back on track! Energy is returning', '2026-08-05T01:33:45.708262', '2026-08-05T01:33:45.708262');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (39, 13, '2026-07-13', 4, 7, 4, 'none', 'Back on track! Energy is returning', '2026-08-05T01:33:45.713488', '2026-08-05T01:33:45.713488');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (40, 13, '2026-07-14', 4, 8, 3, 'none', 'Back on track! Energy is returning', '2026-08-05T01:33:45.717462', '2026-08-05T01:33:45.717462');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (41, 13, '2026-07-15', 5, 8, 3, 'none', 'Back on track! Energy is returning', '2026-08-05T01:33:45.723404', '2026-08-05T01:33:45.723404');
INSERT INTO checkins (id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at, updated_at) VALUES (42, 13, '2026-07-16', 5, 9, 2, 'none', 'Back on track! Energy is returning', '2026-08-05T01:33:45.728150', '2026-08-05T01:33:45.728150');

-- health_metrics: 42 行
DELETE FROM health_metrics;
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (1, 8, '2026-07-10', 65.8, 51.0, 8.0, 21.4, 25.8, 97.4, 13.8, 36.5, 'manual', '2026-08-05T01:33:40.488226');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (2, 8, '2026-07-11', 63.2, 53.0, 7.5, 19.2, 24.1, 97.0, 14.2, 36.6, 'manual', '2026-08-05T01:33:40.494160');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (3, 8, '2026-07-12', 66.5, 52.0, 8.1, 22.0, 26.2, 97.6, 13.9, 36.4, 'manual', '2026-08-05T01:33:40.500121');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (4, 8, '2026-07-13', 64.0, 54.0, 7.8, 20.5, 25.0, 97.3, 14.1, 36.5, 'manual', '2026-08-05T01:33:40.505408');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (5, 8, '2026-07-14', 67.2, 50.0, 8.2, 22.5, 26.5, 97.7, 13.7, 36.4, 'manual', '2026-08-05T01:33:40.510837');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (6, 8, '2026-07-15', 62.5, 55.0, 7.4, 18.8, 23.5, 96.9, 14.4, 36.7, 'manual', '2026-08-05T01:33:40.516359');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (7, 8, '2026-07-16', 64.8, 53.0, 7.7, 20.0, 24.8, 97.2, 14.0, 36.5, 'manual', '2026-08-05T01:33:40.523904');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (8, 9, '2026-07-10', 58.0, 54.0, 7.2, 22.0, 26.0, 97.5, 14.2, 36.4, 'manual', '2026-08-05T01:33:41.192835');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (9, 9, '2026-07-11', 55.0, 55.0, 6.8, 19.0, 24.0, 97.2, 14.5, 36.5, 'manual', '2026-08-05T01:33:41.206642');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (10, 9, '2026-07-12', 52.0, 56.0, 6.5, 17.0, 23.0, 97.0, 14.8, 36.6, 'manual', '2026-08-05T01:33:41.216456');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (11, 9, '2026-07-13', 49.0, 57.0, 6.2, 16.0, 21.0, 96.8, 15.1, 36.7, 'manual', '2026-08-05T01:33:41.228916');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (12, 9, '2026-07-14', 47.0, 58.0, 5.8, 15.0, 20.0, 96.5, 15.3, 36.8, 'manual', '2026-08-05T01:33:41.235918');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (13, 9, '2026-07-15', 44.0, 59.0, 5.5, 14.0, 19.0, 96.3, 15.6, 36.9, 'manual', '2026-08-05T01:33:41.247630');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (14, 9, '2026-07-16', 42.0, 60.0, 5.2, 13.0, 18.0, 96.0, 16.0, 37.0, 'manual', '2026-08-05T01:33:41.257425');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (15, 10, '2026-07-10', 55.0, 56.0, 6.8, 18.0, 22.0, 97.0, 14.5, 36.5, 'manual', '2026-08-05T01:33:42.167221');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (16, 10, '2026-07-11', 50.0, 58.0, 6.2, 16.0, 20.0, 96.7, 15.0, 36.7, 'manual', '2026-08-05T01:33:42.174947');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (17, 10, '2026-07-12', 44.0, 60.0, 5.5, 14.0, 18.0, 96.3, 15.5, 36.9, 'manual', '2026-08-05T01:33:42.184764');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (18, 10, '2026-07-13', 38.0, 63.0, 5.0, 11.0, 15.0, 95.8, 16.2, 37.1, 'manual', '2026-08-05T01:33:42.192553');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (19, 10, '2026-07-14', 35.0, 64.0, 4.5, 10.0, 14.0, 95.5, 16.8, 37.3, 'manual', '2026-08-05T01:33:42.202871');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (20, 10, '2026-07-15', 32.0, 66.0, 4.2, 9.0, 13.0, 95.2, 17.2, 37.4, 'manual', '2026-08-05T01:33:42.211801');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (21, 10, '2026-07-16', 30.0, 67.0, 4.0, 8.0, 12.0, 95.0, 17.5, 37.5, 'manual', '2026-08-05T01:33:42.220816');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (22, 11, '2026-07-10', 48.0, 58.0, 6.0, 15.0, 20.0, 96.8, 15.0, 36.6, 'manual', '2026-08-05T01:33:43.218235');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (23, 11, '2026-07-11', 43.0, 60.0, 5.2, 12.0, 17.0, 96.3, 15.8, 37.0, 'manual', '2026-08-05T01:33:43.231173');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (24, 11, '2026-07-12', 38.0, 63.0, 4.5, 10.0, 14.0, 95.8, 16.5, 37.2, 'manual', '2026-08-05T01:33:43.241334');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (25, 11, '2026-07-13', 33.0, 65.0, 4.0, 8.0, 12.0, 95.2, 17.0, 37.4, 'manual', '2026-08-05T01:33:43.251673');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (26, 11, '2026-07-14', 30.0, 67.0, 3.8, 7.0, 11.0, 95.0, 17.5, 37.6, 'manual', '2026-08-05T01:33:43.261271');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (27, 11, '2026-07-15', 28.0, 68.0, 3.5, 6.0, 10.0, 94.8, 18.0, 37.7, 'manual', '2026-08-05T01:33:43.269949');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (28, 11, '2026-07-16', 26.0, 70.0, 3.2, 5.0, 9.0, 94.5, 18.5, 37.8, 'manual', '2026-08-05T01:33:43.276978');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (29, 12, '2026-07-10', 68.2, 50.0, 8.3, 23.5, 26.5, 97.6, 13.8, 36.4, 'manual', '2026-08-05T01:33:44.348269');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (30, 12, '2026-07-11', 66.5, 51.0, 7.9, 21.0, 25.0, 97.3, 14.0, 36.5, 'manual', '2026-08-05T01:33:44.422214');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (31, 12, '2026-07-12', 69.0, 49.0, 8.4, 24.0, 27.0, 97.8, 13.7, 36.4, 'manual', '2026-08-05T01:33:44.482255');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (32, 12, '2026-07-13', 67.5, 50.0, 8.1, 22.5, 25.8, 97.5, 13.9, 36.4, 'manual', '2026-08-05T01:33:44.503302');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (33, 12, '2026-07-14', 70.2, 48.0, 8.5, 24.5, 27.5, 97.9, 13.6, 36.3, 'manual', '2026-08-05T01:33:44.519982');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (34, 12, '2026-07-15', 65.8, 52.0, 7.8, 20.5, 24.5, 97.2, 14.2, 36.6, 'manual', '2026-08-05T01:33:44.659106');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (35, 12, '2026-07-16', 68.5, 50.0, 8.2, 22.0, 26.0, 97.5, 13.8, 36.4, 'manual', '2026-08-05T01:33:44.730313');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (36, 13, '2026-07-10', 44.0, 60.0, 5.5, 14.0, 18.0, 96.8, 15.5, 36.8, 'manual', '2026-08-05T01:33:45.576108');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (37, 13, '2026-07-11', 46.0, 59.0, 5.8, 15.0, 19.0, 97.0, 15.2, 36.7, 'manual', '2026-08-05T01:33:45.622954');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (38, 13, '2026-07-12', 49.0, 57.0, 6.2, 17.0, 20.0, 97.1, 14.9, 36.6, 'manual', '2026-08-05T01:33:45.636306');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (39, 13, '2026-07-13', 53.0, 55.0, 6.8, 19.0, 22.0, 97.3, 14.6, 36.5, 'manual', '2026-08-05T01:33:45.649209');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (40, 13, '2026-07-14', 57.0, 53.0, 7.2, 21.0, 24.0, 97.5, 14.3, 36.4, 'manual', '2026-08-05T01:33:45.659110');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (41, 13, '2026-07-15', 60.0, 52.0, 7.5, 22.0, 25.0, 97.6, 14.1, 36.4, 'manual', '2026-08-05T01:33:45.677303');
INSERT INTO health_metrics (id, user_id, date, hrv, rhr, sleep_hours, sleep_deep_pct, sleep_rem_pct, spo2, respiratory_rate, skin_temp, source, created_at) VALUES (42, 13, '2026-07-16', 63.0, 51.0, 7.8, 23.0, 26.0, 97.7, 14.0, 36.3, 'manual', '2026-08-05T01:33:45.687363');

-- training_metrics: 42 行
DELETE FROM training_metrics;
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (1, 8, '2026-07-10', 10432.0, 111.5, 28.0, 178.0, 148.0, 52.0, '2026-08-05T01:33:40.491278');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (2, 8, '2026-07-11', 8201.0, 113.8, 29.0, 172.0, 144.0, 42.0, '2026-08-05T01:33:40.497281');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (3, 8, '2026-07-12', 12105.0, 110.2, 27.0, 181.0, 151.0, 58.0, '2026-08-05T01:33:40.502721');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (4, 8, '2026-07-13', 9400.0, 112.5, 30.0, 175.0, 146.0, 47.0, '2026-08-05T01:33:40.507987');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (5, 8, '2026-07-14', 11020.0, 114.0, 28.0, 179.0, 149.0, 55.0, '2026-08-05T01:33:40.513504');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (6, 8, '2026-07-15', 7800.0, 115.5, 30.0, 170.0, 142.0, 40.0, '2026-08-05T01:33:40.520740');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (7, 8, '2026-07-16', 9800.0, 116.2, 31.0, 176.0, 147.0, 50.0, '2026-08-05T01:33:40.527285');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (8, 9, '2026-07-10', 9200.0, 114.5, 29.0, 177.0, 147.0, 48.0, '2026-08-05T01:33:41.199060');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (9, 9, '2026-07-11', 8200.0, 116.0, 28.0, 173.0, 144.0, 43.0, '2026-08-05T01:33:41.212944');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (10, 9, '2026-07-12', 10500.0, 115.2, 30.0, 179.0, 149.0, 51.0, '2026-08-05T01:33:41.224358');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (11, 9, '2026-07-13', 7800.0, 117.5, 27.0, 171.0, 142.0, 40.0, '2026-08-05T01:33:41.232365');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (12, 9, '2026-07-14', 9800.0, 118.0, 29.0, 176.0, 146.0, 49.0, '2026-08-05T01:33:41.241205');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (13, 9, '2026-07-15', 7200.0, 119.2, 28.0, 169.0, 141.0, 38.0, '2026-08-05T01:33:41.251679');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (14, 9, '2026-07-16', 8500.0, 120.5, 30.0, 174.0, 145.0, 44.0, '2026-08-05T01:33:41.261076');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (15, 10, '2026-07-10', 8000.0, 115.0, 28.0, 170.0, 148.0, 45.0, '2026-08-05T01:33:42.171363');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (16, 10, '2026-07-11', 7400.0, 118.0, 28.0, 173.0, 150.0, 42.0, '2026-08-05T01:33:42.180978');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (17, 10, '2026-07-12', 6800.0, 121.0, 27.0, 176.0, 152.0, 39.0, '2026-08-05T01:33:42.188513');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (18, 10, '2026-07-13', 6200.0, 124.0, 27.0, 179.0, 154.0, 36.0, '2026-08-05T01:33:42.196637');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (19, 10, '2026-07-14', 5600.0, 127.0, 26.0, 182.0, 156.0, 33.0, '2026-08-05T01:33:42.207070');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (20, 10, '2026-07-15', 5000.0, 130.0, 26.0, 185.0, 158.0, 30.0, '2026-08-05T01:33:42.215331');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (21, 10, '2026-07-16', 4400.0, 133.0, 25.0, 188.0, 160.0, 27.0, '2026-08-05T01:33:42.227968');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (22, 11, '2026-07-10', 7000.0, 118.0, 26.0, 168.0, 150.0, 40.0, '2026-08-05T01:33:43.223495');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (23, 11, '2026-07-11', 6200.0, 122.0, 25.0, 172.0, 153.0, 36.0, '2026-08-05T01:33:43.235371');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (24, 11, '2026-07-12', 5400.0, 126.0, 25.0, 176.0, 156.0, 32.0, '2026-08-05T01:33:43.245104');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (25, 11, '2026-07-13', 4600.0, 130.0, 24.0, 180.0, 159.0, 28.0, '2026-08-05T01:33:43.255458');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (26, 11, '2026-07-14', 3800.0, 134.0, 24.0, 184.0, 162.0, 24.0, '2026-08-05T01:33:43.265408');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (27, 11, '2026-07-15', 3000.0, 138.0, 23.0, 188.0, 165.0, 20.0, '2026-08-05T01:33:43.273178');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (28, 11, '2026-07-16', 2200.0, 142.0, 23.0, 192.0, 168.0, 16.0, '2026-08-05T01:33:43.282870');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (29, 12, '2026-07-10', 11200.0, 109.0, 27.0, 175.0, 145.0, 58.0, '2026-08-05T01:33:44.361206');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (30, 12, '2026-07-11', 9500.0, 110.5, 28.0, 171.0, 143.0, 50.0, '2026-08-05T01:33:44.453417');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (31, 12, '2026-07-12', 12000.0, 108.2, 27.0, 177.0, 146.0, 62.0, '2026-08-05T01:33:44.492454');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (32, 12, '2026-07-13', 10200.0, 109.5, 28.0, 174.0, 144.0, 53.0, '2026-08-05T01:33:44.507952');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (33, 12, '2026-07-14', 11500.0, 108.8, 27.0, 176.0, 145.0, 59.0, '2026-08-05T01:33:44.532212');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (34, 12, '2026-07-15', 8800.0, 111.0, 29.0, 170.0, 142.0, 46.0, '2026-08-05T01:33:44.678028');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (35, 12, '2026-07-16', 10500.0, 110.0, 28.0, 173.0, 144.0, 54.0, '2026-08-05T01:33:44.859164');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (36, 13, '2026-07-10', 6000.0, 113.0, 28.0, 178.0, 150.0, 40.0, '2026-08-05T01:33:45.609804');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (37, 13, '2026-07-11', 6500.0, 112.0, 28.0, 177.0, 149.0, 42.0, '2026-08-05T01:33:45.629741');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (38, 13, '2026-07-12', 7000.0, 111.0, 29.0, 176.0, 148.0, 44.0, '2026-08-05T01:33:45.643219');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (39, 13, '2026-07-13', 7500.0, 110.0, 29.0, 175.0, 147.0, 46.0, '2026-08-05T01:33:45.654961');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (40, 13, '2026-07-14', 8000.0, 109.0, 29.0, 174.0, 146.0, 48.0, '2026-08-05T01:33:45.663947');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (41, 13, '2026-07-15', 8500.0, 108.0, 30.0, 173.0, 145.0, 50.0, '2026-08-05T01:33:45.683025');
INSERT INTO training_metrics (id, user_id, date, distance, avg_split, avg_spm, max_hr, avg_hr, duration_minutes, created_at) VALUES (42, 13, '2026-07-16', 9000.0, 107.0, 30.0, 172.0, 144.0, 52.0, '2026-08-05T01:33:45.694037');

-- alerts: 15 行
DELETE FROM alerts;
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (1, 9, 'red', 'Physical & Mental Fatigue', 'HRV critically low — burnout risk.', 'active', 3, '2026-08-05T01:33:41.306517', NULL, '2026-08-05T01:33:41.306517', '2026-08-05T01:33:41.306517');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (2, 9, 'yellow', 'Recovery Deficiency', 'HRV declined over recent check-ins — prioritize active recovery today.', 'active', 1, '2026-08-05T01:33:41.311499', NULL, '2026-08-05T01:33:41.311499', '2026-08-05T01:33:41.311499');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (3, 9, 'yellow', 'Sleep Deprivation', 'Reported sleep under 6 hours — emotional vulnerability risk.', 'active', 2, '2026-08-05T01:33:41.317659', NULL, '2026-08-05T01:33:41.317659', '2026-08-05T01:33:41.317659');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (4, 10, 'black', 'URGENT: Athlete in Crisis', 'Multiple severe markers — immediate coach intervention needed.', 'active', 6, '2026-08-05T01:33:42.266287', NULL, '2026-08-05T01:33:42.266287', '2026-08-05T01:33:42.266287');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (5, 10, 'red', 'Mood Decline', 'Mood score dropped significantly — check in personally.', 'active', 5, '2026-08-05T01:33:42.290297', NULL, '2026-08-05T01:33:42.290297', '2026-08-05T01:33:42.290297');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (6, 10, 'red', 'Physical & Mental Fatigue', 'HRV critically low — burnout risk.', 'active', 3, '2026-08-05T01:33:42.295802', NULL, '2026-08-05T01:33:42.295802', '2026-08-05T01:33:42.295802');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (7, 10, 'red', 'Sleep Deprivation — Critical', '3+ nights poor sleep — consider reducing load.', 'active', 4, '2026-08-05T01:33:42.340263', NULL, '2026-08-05T01:33:42.340263', '2026-08-05T01:33:42.340263');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (8, 10, 'yellow', 'Recovery Deficiency', 'HRV declined over recent check-ins — prioritize active recovery today.', 'active', 1, '2026-08-05T01:33:42.345878', NULL, '2026-08-05T01:33:42.345878', '2026-08-05T01:33:42.345878');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (9, 10, 'yellow', 'Sleep Deprivation', 'Reported sleep under 6 hours — emotional vulnerability risk.', 'active', 2, '2026-08-05T01:33:42.355161', NULL, '2026-08-05T01:33:42.355161', '2026-08-05T01:33:42.355161');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (10, 11, 'black', 'URGENT: Athlete in Crisis', 'Multiple severe markers — immediate coach intervention needed.', 'active', 6, '2026-08-05T01:33:43.415382', NULL, '2026-08-05T01:33:43.415382', '2026-08-05T01:33:43.415382');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (11, 11, 'red', 'Mood Decline', 'Mood score dropped significantly — check in personally.', 'active', 5, '2026-08-05T01:33:43.423475', NULL, '2026-08-05T01:33:43.423475', '2026-08-05T01:33:43.423475');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (12, 11, 'red', 'Physical & Mental Fatigue', 'HRV critically low — burnout risk.', 'active', 3, '2026-08-05T01:33:43.430876', NULL, '2026-08-05T01:33:43.430876', '2026-08-05T01:33:43.430876');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (13, 11, 'red', 'Sleep Deprivation — Critical', '3+ nights poor sleep — consider reducing load.', 'active', 4, '2026-08-05T01:33:43.436430', NULL, '2026-08-05T01:33:43.436430', '2026-08-05T01:33:43.436430');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (14, 11, 'yellow', 'Recovery Deficiency', 'HRV declined over recent check-ins — prioritize active recovery today.', 'active', 1, '2026-08-05T01:33:43.445764', NULL, '2026-08-05T01:33:43.445764', '2026-08-05T01:33:43.445764');
INSERT INTO alerts (id, user_id, level, type, message, status, rule_id, triggered_at, resolved_at, created_at, updated_at) VALUES (15, 11, 'yellow', 'Sleep Deprivation', 'Reported sleep under 6 hours — emotional vulnerability risk.', 'active', 2, '2026-08-05T01:33:43.449252', NULL, '2026-08-05T01:33:43.449252', '2026-08-05T01:33:43.449252');

SET FOREIGN_KEY_CHECKS = 1;

-- ✅ 迁移完成，共 201 行数据