CREATE TABLE IF NOT EXISTS town_characters (
    character_id VARCHAR(64) PRIMARY KEY,
    display_name VARCHAR(64) NOT NULL,
    gender VARCHAR(24) NULL,
    birth_year INT NULL,
    marital_status VARCHAR(32) NULL,
    partner_label VARCHAR(128) NULL,
    children_count INT NOT NULL DEFAULT 0,
    career_state VARCHAR(32) NOT NULL DEFAULT 'active',
    work_style VARCHAR(32) NULL,
    personality_notes VARCHAR(500) NULL,
    family_notes VARCHAR(500) NULL,
    traits_json JSON NULL,
    is_core TINYINT(1) NOT NULL DEFAULT 1,
    active TINYINT(1) NOT NULL DEFAULT 1,
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO town_characters
(character_id, display_name, gender, birth_year, marital_status, partner_label, children_count, career_state, work_style, personality_notes, family_notes, traits_json, is_core, active, display_order)
VALUES
('ALE', 'ALE', 'female', 1993, 'partnered', '有老公但未結婚', 1, 'active', 'slacker', '工作時容易摸魚，會聊天、休息或找別的事情做，但必要工作仍會處理。', '有一個小孩；未婚；有長期伴侶。', JSON_OBJECT('workBias', 0.32, 'focus', 0.38, 'social', 0.72, 'restlessness', 0.68), 1, 1, 10),
('MARI', 'MARI', 'female', 1970, NULL, NULL, 2, 'near_retirement', 'slacker', '接近退休，仍然在工作；日常比較會摸魚，不需要一直表現得很忙。', '有兩個小孩。', JSON_OBJECT('workBias', 0.35, 'focus', 0.42, 'social', 0.62, 'restlessness', 0.45), 1, 1, 20),
('NICO', 'NICO', 'male', 1986, 'married', '已婚', 1, 'active', 'diligent', '勤奮工作，工作優先，通常會主動處理事情。', '已婚，有一個小孩；老婆很漂亮，而且有時會來辦公室探班。', JSON_OBJECT('workBias', 0.92, 'focus', 0.90, 'social', 0.55, 'restlessness', 0.20), 1, 1, 30)
ON DUPLICATE KEY UPDATE
    display_name=VALUES(display_name),
    gender=VALUES(gender),
    birth_year=VALUES(birth_year),
    marital_status=VALUES(marital_status),
    partner_label=VALUES(partner_label),
    children_count=VALUES(children_count),
    career_state=VALUES(career_state),
    work_style=VALUES(work_style),
    personality_notes=VALUES(personality_notes),
    family_notes=VALUES(family_notes),
    traits_json=VALUES(traits_json),
    is_core=VALUES(is_core),
    active=VALUES(active),
    display_order=VALUES(display_order);
