-- Создание таблиц для топов с автосбросом
-- Таблицы для хранения выигрышей за день, неделю, месяц и все время

-- Таблица для выигрышей за день (сбрасывается каждые 24 часа)
CREATE TABLE IF NOT EXISTS user_day_winnings (
    user_id BIGINT PRIMARY KEY,
    winnings BIGINT NOT NULL DEFAULT 0,
    last_reset TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Таблица для выигрышей за неделю (сбрасывается каждые 7 дней)
CREATE TABLE IF NOT EXISTS user_week_winnings (
    user_id BIGINT PRIMARY KEY,
    winnings BIGINT NOT NULL DEFAULT 0,
    last_reset TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Таблица для выигрышей за месяц (сбрасывается каждые 30 дней)
CREATE TABLE IF NOT EXISTS user_month_winnings (
    user_id BIGINT PRIMARY KEY,
    winnings BIGINT NOT NULL DEFAULT 0,
    last_reset TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Таблица для выигрышей за все время (не сбрасывается)
CREATE TABLE IF NOT EXISTS user_all_time_winnings (
    user_id BIGINT PRIMARY KEY,
    winnings BIGINT NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_day_winnings_winnings ON user_day_winnings(winnings DESC);
CREATE INDEX IF NOT EXISTS idx_week_winnings_winnings ON user_week_winnings(winnings DESC);
CREATE INDEX IF NOT EXISTS idx_month_winnings_winnings ON user_month_winnings(winnings DESC);
CREATE INDEX IF NOT EXISTS idx_all_time_winnings_winnings ON user_all_time_winnings(winnings DESC);

-- Функция для сброса дневных выигрышей
CREATE OR REPLACE FUNCTION reset_day_winnings()
RETURNS void AS $$
BEGIN
    UPDATE user_day_winnings
    SET winnings = 0, last_reset = NOW()
    WHERE last_reset < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;

-- Функция для сброса недельных выигрышей
CREATE OR REPLACE FUNCTION reset_week_winnings()
RETURNS void AS $$
BEGIN
    UPDATE user_week_winnings
    SET winnings = 0, last_reset = NOW()
    WHERE last_reset < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Функция для сброса месячных выигрышей
CREATE OR REPLACE FUNCTION reset_month_winnings()
RETURNS void AS $$
BEGIN
    UPDATE user_month_winnings
    SET winnings = 0, last_reset = NOW()
    WHERE last_reset < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Функция для добавления выигрышей пользователю
CREATE OR REPLACE FUNCTION add_user_winnings(
    p_user_id BIGINT,
    p_amount BIGINT
)
RETURNS void AS $$
BEGIN
    -- Обновляем или создаем запись для дня
    INSERT INTO user_day_winnings (user_id, winnings, last_reset)
    VALUES (p_user_id, p_amount, NOW())
    ON CONFLICT (user_id) DO UPDATE
    SET winnings = user_day_winnings.winnings + p_amount
    WHERE user_day_winnings.last_reset >= NOW() - INTERVAL '24 hours';
    
    -- Если прошло больше 24 часов, сбрасываем
    UPDATE user_day_winnings
    SET winnings = p_amount, last_reset = NOW()
    WHERE user_id = p_user_id AND last_reset < NOW() - INTERVAL '24 hours';
    
    -- Обновляем или создаем запись для недели
    INSERT INTO user_week_winnings (user_id, winnings, last_reset)
    VALUES (p_user_id, p_amount, NOW())
    ON CONFLICT (user_id) DO UPDATE
    SET winnings = user_week_winnings.winnings + p_amount
    WHERE user_week_winnings.last_reset >= NOW() - INTERVAL '7 days';
    
    -- Если прошло больше 7 дней, сбрасываем
    UPDATE user_week_winnings
    SET winnings = p_amount, last_reset = NOW()
    WHERE user_id = p_user_id AND last_reset < NOW() - INTERVAL '7 days';
    
    -- Обновляем или создаем запись для месяца
    INSERT INTO user_month_winnings (user_id, winnings, last_reset)
    VALUES (p_user_id, p_amount, NOW())
    ON CONFLICT (user_id) DO UPDATE
    SET winnings = user_month_winnings.winnings + p_amount
    WHERE user_month_winnings.last_reset >= NOW() - INTERVAL '30 days';
    
    -- Если прошло больше 30 дней, сбрасываем
    UPDATE user_month_winnings
    SET winnings = p_amount, last_reset = NOW()
    WHERE user_id = p_user_id AND last_reset < NOW() - INTERVAL '30 days';
    
    -- Обновляем или создаем запись для всех времен
    INSERT INTO user_all_time_winnings (user_id, winnings)
    VALUES (p_user_id, p_amount)
    ON CONFLICT (user_id) DO UPDATE
    SET winnings = user_all_time_winnings.winnings + p_amount;
END;
$$ LANGUAGE plpgsql;

