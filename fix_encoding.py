import json

# Читаем файл с BOM и сохраняем без BOM
def fix_file(filename):
    try:
        # Читаем с utf-8-sig (убирает BOM автоматически)
        with open(filename, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        
        # Сохраняем как чистый utf-8 без BOM
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Файл {filename} исправлен")
    except Exception as e:
        print(f"❌ Ошибка с файлом {filename}: {e}")

# Исправляем оба файла
fix_file("situations.json")
fix_file("answers.json")
print("Готово!")
