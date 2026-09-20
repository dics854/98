import sqlite3

# Создаём базу данных
conn = sqlite3.connect('backup_restore_test.db')
cursor = conn.cursor()

# Создаём таблицу users
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    role TEXT,
    class_number INTEGER,
    created_at DATETIME NOT NULL,
    tokens_limit INTEGER DEFAULT 400000,
    tokens_used INTEGER DEFAULT 0,
    tokens_reset_date DATETIME,
    tokens_frozen BOOLEAN DEFAULT 0
)
''')

# Создаём таблицу access_codes
cursor.execute('''
CREATE TABLE IF NOT EXISTS access_codes (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    code_name TEXT,
    duration_days INTEGER NOT NULL,
    created_by BIGINT NOT NULL,
    activated_by INTEGER,
    is_active BOOLEAN DEFAULT 1,
    is_blocked BOOLEAN DEFAULT 0,
    created_at DATETIME NOT NULL,
    activated_at DATETIME,
    expires_at DATETIME,
    FOREIGN KEY (activated_by) REFERENCES users (id)
)
''')

# Создаём таблицу tasks
cursor.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    task_text TEXT NOT NULL,
    topic TEXT,
    difficulty TEXT DEFAULT 'medium',
    student_answer TEXT,
    is_correct BOOLEAN,
    ai_explanation TEXT,
    created_at DATETIME NOT NULL,
    completed_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users (id)
)
''')

# Создаём таблицу progress
cursor.execute('''
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    total_tasks INTEGER DEFAULT 0,
    solved_tasks INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    mistakes INTEGER DEFAULT 0,
    last_activity DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
)
''')

# Создаём таблицу parent_child
cursor.execute('''
CREATE TABLE IF NOT EXISTS parent_child (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER NOT NULL,
    child_id INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES users (id),
    FOREIGN KEY (child_id) REFERENCES users (id)
)
''')

# Вставляем пользователей
users = [
    (1, 5363699673, 'DICSITRen2200', 'Miron', None, 'student', 9, '2026-08-30T13:41:53.149402'),
    (2, 8829930689, 'dvedian', 'Татьяна', None, 'student', 7, '2026-08-30T13:43:45.317329'),
    (3, 7032356257, 'ln701', 'Элен', None, 'student', 8, '2026-08-30T13:44:13.987803'),
    (4, 7898440462, None, 'Натали', None, None, None, '2026-09-01T14:38:00.163714'),
    (5, 7383701789, 'Dora666_bobik', 'Бобик мобик🏳️‍🌈', None, 'student', 7, '2026-09-02T12:03:42.608833'),
    (6, 8658365831, 'hawhee12', 'jackson', None, 'student', 7, '2026-09-02T12:06:49.592585'),
    (7, 7783602065, 'VIP_SOFA216', 'Sofа', None, 'student', 5, '2026-09-02T12:53:46.859159'),
    (8, 1546154711, None, 'Милодовская', 'Алла', None, None, '2026-09-04T05:12:39.043160')
]

for user in users:
    cursor.execute('''
        INSERT OR REPLACE INTO users (id, telegram_id, username, first_name, last_name, role, class_number, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', user)

# Вставляем коды доступа (подписки)
access_codes = [
    (1, 'DIRECT_7032356257_1788097507.293857', None, 30, 8829930689, 3, False, False, 
     '2026-08-30T13:45:07.295615', '2026-08-30T13:45:07.293877', '2026-09-29T13:45:07.293880'),
    (2, 'DIRECT_8658365831_1788350968.186529', None, 30, 8829930689, 6, False, False,
     '2026-09-02T12:09:28.191058', '2026-09-02T12:09:28.188008', '2026-10-02T12:09:28.188015'),
    (3, 'DIRECT_7383701789_1788351046.04272', None, 30, 8829930689, 5, False, False,
     '2026-09-02T12:10:46.043413', '2026-09-02T12:10:46.042744', '2026-10-02T12:10:46.042747'),
    (4, 'DIRECT_7783602065_1788353674.215101', None, 30, 8829930689, 7, False, False,
     '2026-09-02T12:54:34.215591', '2026-09-02T12:54:34.215117', '2026-10-02T12:54:34.215120')
]

for code in access_codes:
    cursor.execute('''
        INSERT OR REPLACE INTO access_codes 
        (id, code, code_name, duration_days, created_by, activated_by, is_active, is_blocked, 
         created_at, activated_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', code)

# Вставляем задачи (первые 5 для примера)
tasks = [
    (1, 3, 'В цветнике растут только тюльпаны, гиацинты и пионы. Их количества относятся как 2 : 6 : 8 соответственно. Всего в цветнике 64 растения. Сколько пионов растет в цветнике?',
     'Решается с репетитором', 'medium', None, False, 'Занятие завершено до получения правильного ответа',
     '2026-08-30T13:46:43.970311', '2026-08-30T13:49:15.265194'),
    (2, 1, 'обьясни тему из 6 класса', 'Решается с репетитором', 'medium', None, False,
     'Занятие завершено до получения правильного ответа', '2026-08-31T12:58:54.767629', '2026-08-31T12:59:04.844840'),
    (3, 3, 'В двух сосудах 57 литров жидкости. Если 5% жидкости из первого сосуда перелить во второй, то в обоих сосудах окажется одинаковое количество жидкости. Сколько литров жидкости было во втором сосуде первоначально?',
     'Решается с репетитором', 'medium', None, False, 'Занятие завершено до получения правильного ответа',
     '2026-08-31T13:05:03.253678', '2026-08-31T13:09:34.897340'),
    (4, 2, 'Найдите площадь квадрата, длина стороны которого равна 5 см', 'Решается с репетитором', 
     'medium', None, None, None, '2026-09-02T07:45:29.815730', None),
    (5, 1, 'электрон помоги с задачей', 'Решается с репетитором', 'medium', None, False,
     'Занятие завершено до получения правильного ответа', '2026-09-02T12:36:06.451714', '2026-09-02T12:37:50.785436')
]

for task in tasks:
    cursor.execute('''
        INSERT OR REPLACE INTO tasks 
        (id, user_id, task_text, topic, difficulty, student_answer, is_correct, ai_explanation, 
         created_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', task)

# Вставляем прогресс
progress = [
    (1, 1, 5, 3, 2, 1, '2026-09-02T15:27:57', '2026-08-30T13:41:56'),
    (2, 3, 3, 2, 1, 1, '2026-08-31T13:09:34', '2026-08-30T13:46:38'),
    (3, 2, 2, 1, 1, 0, '2026-09-04T06:16:32', '2026-09-02T07:01:51'),
    (4, 6, 10, 8, 5, 3, '2026-09-02T15:40:50', '2026-09-02T12:09:52'),
    (5, 7, 3, 2, 1, 1, '2026-09-04T12:58:41', '2026-09-02T12:54:51')
]

for prog in progress:
    cursor.execute('''
        INSERT OR REPLACE INTO progress 
        (id, user_id, total_tasks, solved_tasks, correct_answers, mistakes, last_activity, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', prog)

conn.commit()
conn.close()

print('✅ Файл backup_restore_test.db создан!')
print('📁 Путь: backup_restore_test.db')
print('')
print('📊 Содержимое:')
print('  👥 8 пользователей')
print('  🔑 4 кода доступа (подписки с датами истечения)')
print('  📝 5 задач')
print('  📊 5 записей прогресса')
print('')
print('🎯 Что будет восстановлено:')
print('  ✅ Пользователи (username, имя, класс)')
print('  ✅ Подписки (сколько дней осталось)')
print('  ✅ Решённые задачи')
print('  ✅ Статистика прогресса')
print('  ✅ Токены (лимит и использовано)')
print('')
print('📥 Теперь отправьте этот файл боту через админ-панель:')
print('   /admin → 📥 Восстановить из бэкапа → прикрепите файл')


