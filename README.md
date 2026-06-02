# KidLock — Этап 1: Блокировка по расписанию

## Структура

```
kidlock/
├── agent/
│   ├── agent.py        ← главный процесс (запускать от администратора)
│   ├── scheduler.py    ← логика расписания и лимитов
│   ├── locker.py       ← блокировка Windows
│   ├── notifier.py     ← предупреждения (всплывающие окна)
│   ├── config.json     ← расписание (редактируй здесь)
│   └── usage.json      ← автоматически создаётся (учёт времени)
└── requirements.txt
```

---

## Быстрый старт

### 1. Установи Python 3.10+
https://python.org — при установке отметь "Add to PATH"

### 2. Установи зависимости
```cmd
pip install -r requirements.txt
```

### 3. Настрой расписание
Открой `agent/config.json` и задай:
- `allowed_hours` — в какое время можно работать (по дням)
- `daily_limit_minutes` — сколько минут в день разрешено
- `warning_seconds` — за сколько секунд показывать предупреждение (по умолчанию 120)

### 4. Запусти агент (от администратора!)
```cmd
python agent/agent.py
```

---

## Запуск как Windows-сервис (рекомендуется)

Сервис запускается автоматически при старте Windows и работает в фоне.

```cmd
# Установить сервис (от администратора)
python agent/agent.py install

# Запустить
python agent/agent.py start

# Остановить
python agent/agent.py stop

# Удалить
python agent/agent.py remove
```

После установки сервис виден в `services.msc` как "KidLock Parental Control Agent".

---

## Пример config.json

```json
{
  "warning_seconds": 120,
  "check_interval_seconds": 30,
  "schedule": {
    "allowed_hours": {
      "monday":    { "start": "14:00", "end": "20:00" },
      "tuesday":   { "start": "14:00", "end": "20:00" },
      "wednesday": { "start": "14:00", "end": "20:00" },
      "thursday":  { "start": "14:00", "end": "20:00" },
      "friday":    { "start": "14:00", "end": "22:00" },
      "saturday":  { "start": "10:00", "end": "22:00" },
      "sunday":    { "start": "10:00", "end": "21:00" }
    },
    "daily_limit_minutes": {
      "monday":    90,
      "tuesday":   90,
      "wednesday": 90,
      "thursday":  90,
      "friday":    180,
      "saturday":  240,
      "sunday":    180
    }
  }
}
```

---

## Как работает блокировка

1. Каждые `check_interval_seconds` агент проверяет: разрешено ли сейчас работать
2. Если разрешено — следит за временем до конца
3. За 120 / 60 / 30 секунд до конца — показывает всплывающее предупреждение
4. Когда время вышло — принудительный выход из сессии (`shutdown /l /f`)

---

## Логи

Все события записываются в `agent/kidlock.log`

---

## Этап 2 (следующий шаг)

Добавим FastAPI-сервер и веб-панель для управления:
- Просмотр текущего статуса
- Изменение расписания
- Добавление времени удалённо
- Авторизация (родитель / ребёнок)
