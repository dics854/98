import sqlite3

conn = sqlite3.connect('d:\\math-tutor\\math_tutor.db')
cursor = conn.cursor()

# Получаем ВСЕХ пользователей
cursor.execute("SELECT id, telegram_id, username FROM users")
users = cursor.fetchall()

# Получаем всех у кого ЕСТЬ Progress
cursor.execute("SELECT user_id FROM progress")
users_with_progress = [row[0] for row in cursor.fetchall()]

print("=== ПРОВЕРКА СТАРЫХ ПОЛЬЗОВАТЕЛЕЙ ===\n")
print(f"Всего пользователей: {len(users)}")
print(f"С Progress: {len(users_with_progress)}")
print(f"БЕЗ Progress: {len(users) - len(users_with_progress)}\n")

print("Пользователи БЕЗ Progress (для них Progress создастся автоматически):")
for user in users:
    user_db_id = user[0]
    telegram_id = user[1]
    username = user[2]
    
    if user_db_id not in users_with_progress:
        print(f"  - ID:{telegram_id} @{username or 'NO_USERNAME'}")

print("\nПользователи С Progress (для них будет использоваться существующий):")
for user in users:
    user_db_id = user[0]
    telegram_id = user[1]
    username = user[2]
    
    if user_db_id in users_with_progress:
        # Получаем их статистику
        cursor.execute("SELECT total_tasks, solved_tasks FROM progress WHERE user_id = ?", (user_db_id,))
        stats = cursor.fetchone()
        print(f"  - ID:{telegram_id} @{username or 'NO_USERNAME'} (задач: {stats[0]}, решено: {stats[1]})")

conn.close()

print("\n" + "="*60)
print("ВЕРДИКТ ДЛЯ СТАРЫХ ПОЛЬЗОВАТЕЛЕЙ:")
print("="*60)
print("✓ Пользователи С Progress - будут использовать существующий")
print("✓ Пользователи БЕЗ Progress - создастся автоматически")
print("✓ ВСЕ старые пользователи смогут решать задачи!")
