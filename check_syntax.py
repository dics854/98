#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Быстрая проверка синтаксиса всех файлов"""

import ast
import sys

files = [
    'main.py',
    'config.py',
    'handlers/__init__.py',
    'handlers/start.py',
    'handlers/student.py',
    'handlers/admin.py',
    'handlers/admin_additions.py',
    'services/user_service.py',
    'services/access_service.py',
    'services/token_service.py',
    'services/backup_service.py',
    'models/user.py',
    'models/progress.py',
    'models/task.py',
    'models/access_code.py',
    'middlewares/db_middleware.py',
    'middlewares/access_middleware.py',
]

print("="*60)
print("ПРОВЕРКА СИНТАКСИСА")
print("="*60)

errors = []
ok = []

for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            code = file.read()
            ast.parse(code)
        ok.append(f)
        print(f"✅ {f}")
    except SyntaxError as e:
        errors.append((f, e.lineno, e.msg))
        print(f"❌ {f} - ОШИБКА на строке {e.lineno}: {e.msg}")
    except FileNotFoundError:
        print(f"⚠️ {f} - НЕ НАЙДЕН")
    except Exception as e:
        errors.append((f, 0, str(e)))
        print(f"❌ {f} - ОШИБКА: {e}")

print("\n" + "="*60)
if errors:
    print(f"❌ НАЙДЕНО ОШИБОК: {len(errors)}")
    print("="*60)
    for f, line, msg in errors:
        print(f"  {f}:{line} - {msg}")
    sys.exit(1)
else:
    print(f"✅ ВСЕ ФАЙЛЫ OK ({len(ok)}/{len(files)})")
    print("="*60)
    print("\n🚀 СИНТАКСИС КОРРЕКТЕН - МОЖНО ЗАПУСКАТЬ!")
    sys.exit(0)
