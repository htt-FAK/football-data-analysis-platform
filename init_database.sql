-- ============================================================
-- 09体育赛事数据采集与分析 - 数据库建表脚本
-- 数据库: root1 @ 118.126.102.143
-- 用户: root1
-- 注意: 不删除现有表，仅新增体育相关表
-- ============================================================

-- 连接到数据库
-- mysql -h 118.126.102.143 -u root1 -pxiangmushu root1

-- ============================================================
-- 1. 联赛表
-- ============================================================
CREATE TABLE IF NOT EXISTS leagues (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '联赛名称（如：英超、世界杯）',
    country VARCHAR(50) COMMENT '所属国家',
    logo_url VARCHAR(255) COMMENT '联赛logo URL',
    type VARCHAR(20) DEFAULT 'league' COMMENT '类型（league/tournament）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 增量同步字段
    data_source VARCHAR(50) COMMENT '数据来源(源系统编码)',
    source_id VARCHAR(100) COMMENT '来源系统原始ID',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据最后更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    data_hash VARCHAR(64) COMMENT '数据哈希(SHA256,用于去重)'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='联赛表';

-- ============================================================
-- 2. 赛季表
-- ============================================================
CREATE TABLE IF NOT EXISTS seasons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    league_id INT NOT NULL COMMENT '联赛ID',
    name VARCHAR(50) NOT NULL COMMENT '赛季名称（如：2025-2026）',
    start_date DATE COMMENT '赛季开始日期',
    end_date DATE COMMENT '赛季结束日期',
    current_matchday INT DEFAULT 0 COMMENT '当前轮次',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 增量同步字段
    data_source VARCHAR(50) COMMENT '数据来源(源系统编码)',
    source_id VARCHAR(100) COMMENT '来源系统原始ID',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据最后更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    data_hash VARCHAR(64) COMMENT '数据哈希(SHA256,用于去重)',
    FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE,
    INDEX idx_league (league_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='赛季表';

-- ============================================================
-- 3. 球队表
-- ============================================================
CREATE TABLE IF NOT EXISTS teams (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '球队名称',
    full_name VARCHAR(200) COMMENT '球队全称',
    country VARCHAR(50) COMMENT '所属国家',
    logo_url VARCHAR(255) COMMENT '队徽URL',
    stadium VARCHAR(100) COMMENT '主场名称',
    coach VARCHAR(100) COMMENT '主教练',
    founded_year INT COMMENT '成立年份',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 增量同步字段
    data_source VARCHAR(50) COMMENT '数据来源(源系统编码)',
    source_id VARCHAR(100) COMMENT '来源系统原始ID',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据最后更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    data_hash VARCHAR(64) COMMENT '数据哈希(SHA256,用于去重)',
    INDEX idx_name (name),
    INDEX idx_country (country)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='球队表';

-- ============================================================
-- 4. 球员表
-- ============================================================
CREATE TABLE IF NOT EXISTS players (
    id INT AUTO_INCREMENT PRIMARY KEY,
    team_id INT COMMENT '所属球队ID',
    name VARCHAR(100) NOT NULL COMMENT '球员姓名',
    position VARCHAR(20) COMMENT '位置（GK/DF/MF/FW）',
    shirt_number INT COMMENT '球衣号码',
    nationality VARCHAR(50) COMMENT '国籍',
    birth_date DATE COMMENT '出生日期',
    height INT COMMENT '身高(cm)',
    weight INT COMMENT '体重(kg)',
    photo_url VARCHAR(255) COMMENT '头像URL',
    -- 门将专属字段
    saves INT DEFAULT 0 COMMENT '扑救数(GK)',
    save_rate FLOAT DEFAULT 0 COMMENT '扑救率(GK)',
    xcs FLOAT DEFAULT 0 COMMENT '预期失球(GK)',
    sweeper_actions INT DEFAULT 0 COMMENT '出击次数(GK)',
    -- 六边图评分字段（按位置差异化展示）
    atk_score FLOAT DEFAULT 0 COMMENT '进攻维度评分',
    org_score FLOAT DEFAULT 0 COMMENT '组织维度评分',
    def_score FLOAT DEFAULT 0 COMMENT '防守维度评分',
    gk_score FLOAT DEFAULT 0 COMMENT '门线维度评分(GK)',
    phy_score FLOAT DEFAULT 0 COMMENT '身体/运动维度评分',
    dis_score FLOAT DEFAULT 0 COMMENT '纪律维度评分',
    overall_rating FLOAT DEFAULT 0 COMMENT '综合评分(按位置权重计算)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 增量同步字段
    data_source VARCHAR(50) COMMENT '数据来源(源系统编码)',
    source_id VARCHAR(100) COMMENT '来源系统原始ID',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据最后更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    data_hash VARCHAR(64) COMMENT '数据哈希(SHA256,用于去重)',
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL,
    INDEX idx_team (team_id),
    INDEX idx_name (name),
    INDEX idx_position (position)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='球员表';

-- ============================================================
-- 5. 比赛表
-- ============================================================
CREATE TABLE IF NOT EXISTS matches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    season_id INT COMMENT '赛季ID',
    league_id INT COMMENT '联赛ID',
    matchday INT COMMENT '轮次',
    home_team_id INT COMMENT '主队ID',
    away_team_id INT COMMENT '客队ID',
    home_score INT COMMENT '主队比分',
    away_score INT COMMENT '客队比分',
    home_score_ht INT COMMENT '主队半场比分',
    away_score_ht INT COMMENT '客队半场比分',
    status VARCHAR(20) DEFAULT 'scheduled' COMMENT '状态（scheduled/playing/finished）',
    match_date DATETIME COMMENT '比赛时间',
    venue VARCHAR(100) COMMENT '比赛场地',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 增量同步字段
    data_source VARCHAR(50) COMMENT '数据来源(源系统编码)',
    source_id VARCHAR(100) COMMENT '来源系统原始ID',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据最后更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    data_hash VARCHAR(64) COMMENT '数据哈希(SHA256,用于去重)',
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE SET NULL,
    FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE SET NULL,
    FOREIGN KEY (home_team_id) REFERENCES teams(id) ON DELETE SET NULL,
    FOREIGN KEY (away_team_id) REFERENCES teams(id) ON DELETE SET NULL,
    INDEX idx_league_matchday (league_id, matchday),
    INDEX idx_date (match_date),
    INDEX idx_status (status),
    INDEX idx_teams (home_team_id, away_team_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='比赛表';

-- ============================================================
-- 6. 积分榜表
-- ============================================================
CREATE TABLE IF NOT EXISTS standings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    season_id INT COMMENT '赛季ID',
    team_id INT COMMENT '球队ID',
    position INT COMMENT '排名',
    played INT DEFAULT 0 COMMENT '已赛场次',
    won INT DEFAULT 0 COMMENT '胜',
    drawn INT DEFAULT 0 COMMENT '平',
    lost INT DEFAULT 0 COMMENT '负',
    goals_for INT DEFAULT 0 COMMENT '进球',
    goals_against INT DEFAULT 0 COMMENT '失球',
    goal_diff INT DEFAULT 0 COMMENT '净胜球',
    points INT DEFAULT 0 COMMENT '积分',
    form VARCHAR(50) COMMENT '近期战绩（如：WWDLW）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 增量同步字段
    data_source VARCHAR(50) COMMENT '数据来源(源系统编码)',
    source_id VARCHAR(100) COMMENT '来源系统原始ID',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据最后更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    data_hash VARCHAR(64) COMMENT '数据哈希(SHA256,用于去重)',
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    UNIQUE KEY uk_season_team (season_id, team_id),
    INDEX idx_season_position (season_id, position)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='积分榜表';

-- ============================================================
-- 7. 比赛事件表
-- ============================================================
CREATE TABLE IF NOT EXISTS match_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id INT NOT NULL COMMENT '比赛ID',
    minute INT COMMENT '比赛分钟',
    event_type VARCHAR(20) COMMENT '事件类型（goal/card/substitution/var）',
    team_id INT COMMENT '球队ID',
    player_id INT COMMENT '球员ID',
    detail VARCHAR(200) COMMENT '事件详情',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- 增量同步字段
    data_source VARCHAR(50) COMMENT '数据来源(源系统编码)',
    source_id VARCHAR(100) COMMENT '来源系统原始ID',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据最后更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    data_hash VARCHAR(64) COMMENT '数据哈希(SHA256,用于去重)',
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL,
    INDEX idx_match (match_id),
    INDEX idx_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='比赛事件表';

-- ============================================================
-- 8. 球员赛季统计表
-- ============================================================
CREATE TABLE IF NOT EXISTS player_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    player_id INT NOT NULL COMMENT '球员ID',
    season_id INT NOT NULL COMMENT '赛季ID',
    appearances INT DEFAULT 0 COMMENT '出场次数',
    goals INT DEFAULT 0 COMMENT '进球',
    assists INT DEFAULT 0 COMMENT '助攻',
    yellow_cards INT DEFAULT 0 COMMENT '黄牌',
    red_cards INT DEFAULT 0 COMMENT '红牌',
    minutes_played INT DEFAULT 0 COMMENT '出场时间(分钟)',
    shots INT DEFAULT 0 COMMENT '射门次数',
    shots_on_target INT DEFAULT 0 COMMENT '射正次数',
    xg FLOAT DEFAULT 0 COMMENT '预期进球',
    xa FLOAT DEFAULT 0 COMMENT '预期助攻',
    passes INT DEFAULT 0 COMMENT '传球次数',
    pass_accuracy FLOAT DEFAULT 0 COMMENT '传球成功率',
    tackles INT DEFAULT 0 COMMENT '抢断',
    interceptions INT DEFAULT 0 COMMENT '拦截',
    rating FLOAT DEFAULT 0 COMMENT '综合评分',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 增量同步字段
    data_source VARCHAR(50) COMMENT '数据来源(源系统编码)',
    source_id VARCHAR(100) COMMENT '来源系统原始ID',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据最后更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    data_hash VARCHAR(64) COMMENT '数据哈希(SHA256,用于去重)',
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
    UNIQUE KEY uk_player_season (player_id, season_id),
    INDEX idx_season_goals (season_id, goals DESC),
    INDEX idx_season_assists (season_id, assists DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='球员赛季统计表';

-- ============================================================
-- 9. 射门数据表
-- ============================================================
CREATE TABLE IF NOT EXISTS shots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id INT COMMENT '比赛ID',
    player_id INT COMMENT '球员ID',
    team_id INT COMMENT '球队ID',
    minute INT COMMENT '比赛分钟',
    x_coord FLOAT COMMENT '射门X坐标(0-100)',
    y_coord FLOAT COMMENT '射门Y坐标(0-100)',
    result VARCHAR(20) COMMENT '结果（goal/missed/saved/blocked）',
    shot_type VARCHAR(20) COMMENT '射门类型（foot/head/other）',
    situation VARCHAR(20) COMMENT '情境（open_play/corner/free_kick/penalty）',
    xg FLOAT COMMENT '该射门xG值',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- 增量同步字段
    data_source VARCHAR(50) COMMENT '数据来源(源系统编码)',
    source_id VARCHAR(100) COMMENT '来源系统原始ID',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据最后更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    data_hash VARCHAR(64) COMMENT '数据哈希(SHA256,用于去重)',
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL,
    INDEX idx_match (match_id),
    INDEX idx_player (player_id),
    INDEX idx_team (team_id),
    INDEX idx_result (result)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='射门数据表';

-- ============================================================
-- 10. 球队赛季统计表（额外，用于攻防分析）
-- ============================================================
CREATE TABLE IF NOT EXISTS team_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    team_id INT NOT NULL COMMENT '球队ID',
    season_id INT NOT NULL COMMENT '赛季ID',
    matches_played INT DEFAULT 0 COMMENT '比赛场次',
    wins INT DEFAULT 0 COMMENT '胜场',
    draws INT DEFAULT 0 COMMENT '平场',
    losses INT DEFAULT 0 COMMENT '负场',
    goals_for INT DEFAULT 0 COMMENT '进球总数',
    goals_against INT DEFAULT 0 COMMENT '失球总数',
    xg_for FLOAT DEFAULT 0 COMMENT '预期进球总数',
    xg_against FLOAT DEFAULT 0 COMMENT '预期失球总数',
    possession FLOAT DEFAULT 0 COMMENT '场均控球率(%)',
    shots_total INT DEFAULT 0 COMMENT '射门总数',
    shots_on_target_total INT DEFAULT 0 COMMENT '射正总数',
    passes_total INT DEFAULT 0 COMMENT '传球总数',
    pass_accuracy FLOAT DEFAULT 0 COMMENT '传球成功率(%)',
    corners INT DEFAULT 0 COMMENT '角球数',
    fouls INT DEFAULT 0 COMMENT '犯规数',
    clean_sheets INT DEFAULT 0 COMMENT '零封场次',
    attack_rating FLOAT DEFAULT 0 COMMENT '进攻评分(0-100)',
    defense_rating FLOAT DEFAULT 0 COMMENT '防守评分(0-100)',
    overall_rating FLOAT DEFAULT 0 COMMENT '综合评分(0-100)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 增量同步字段
    data_source VARCHAR(50) COMMENT '数据来源(源系统编码)',
    source_id VARCHAR(100) COMMENT '来源系统原始ID',
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据最后更新时间',
    version INT DEFAULT 1 COMMENT '版本号(乐观锁)',
    data_hash VARCHAR(64) COMMENT '数据哈希(SHA256,用于去重)',
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
    UNIQUE KEY uk_team_season (team_id, season_id),
    INDEX idx_season_rating (season_id, overall_rating DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='球队赛季统计表';

-- ============================================================
-- 11. 数据源登记表（管理各爬虫数据源配置）
-- ============================================================
CREATE TABLE IF NOT EXISTS data_sources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_code VARCHAR(50) NOT NULL COMMENT '数据源编码(如:dongqiudi/fbref/understat/football_data)',
    name VARCHAR(100) NOT NULL COMMENT '数据源名称',
    type VARCHAR(20) COMMENT '类型(api/web/crawler)',
    base_url VARCHAR(255) COMMENT '基础URL',
    api_key VARCHAR(255) COMMENT 'API密钥',
    priority INT DEFAULT 0 COMMENT '优先级(数字越小优先级越高)',
    enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态(active/inactive/error)',
    last_crawl_at DATETIME COMMENT '最后一次抓取时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_source_code (source_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据源登记表';

-- ============================================================
-- 12. 抓取日志表（记录每次抓取任务执行情况）
-- ============================================================
CREATE TABLE IF NOT EXISTS crawl_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT COMMENT '数据源ID',
    target VARCHAR(200) COMMENT '抓取目标(如:赛程/积分榜/球员统计)',
    start_time DATETIME COMMENT '抓取开始时间',
    end_time DATETIME COMMENT '抓取结束时间',
    fetched INT DEFAULT 0 COMMENT '抓取记录数',
    updated INT DEFAULT 0 COMMENT '更新记录数',
    failed INT DEFAULT 0 COMMENT '失败记录数',
    cost_ms INT COMMENT '耗时(毫秒)',
    status VARCHAR(20) COMMENT '状态(success/running/failed)',
    error_msg TEXT COMMENT '错误信息',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES data_sources(id) ON DELETE SET NULL,
    INDEX idx_source (source_id),
    INDEX idx_status (status),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='抓取日志表';

-- ============================================================
-- 验证
-- ============================================================
SHOW TABLES;
SELECT ' leagues' AS table_name, COUNT(*) AS cols FROM information_schema.columns WHERE table_schema='root1' AND table_name='leagues'
UNION SELECT 'seasons', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='seasons'
UNION SELECT 'teams', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='teams'
UNION SELECT 'players', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='players'
UNION SELECT 'matches', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='matches'
UNION SELECT 'standings', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='standings'
UNION SELECT 'match_events', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='match_events'
UNION SELECT 'player_stats', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='player_stats'
UNION SELECT 'shots', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='shots'
UNION SELECT 'team_stats', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='team_stats'
UNION SELECT 'data_sources', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='data_sources'
UNION SELECT 'crawl_logs', COUNT(*) FROM information_schema.columns WHERE table_schema='root1' AND table_name='crawl_logs';
