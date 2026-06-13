# Деплой на Railway

## 1. Создай бота в Telegram

1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь `/newbot`, задай имя и username
3. Скопируй токен — он вида `1234567890:ABCdef...`

## 2. Узнай свой Telegram chat_id

1. Напиши боту [@userinfobot](https://t.me/userinfobot)
2. Он пришлёт твой `id` — это и есть `CHAT_ID`

## 3. Загрузи код на GitHub

```bash
cd tg-planner-bot
git init
git add .
git commit -m "init"
# создай репозиторий на github.com, затем:
git remote add origin https://github.com/ВАШ_ЮЗЕР/tg-planner-bot.git
git push -u origin main
```

## 4. Задеплой на Railway

1. Зайди на [railway.app](https://railway.app) → Sign in with GitHub
2. **New Project** → **Deploy from GitHub repo** → выбери репозиторий
3. Перейди в **Variables** и добавь:
   - `BOT_TOKEN` = твой токен от BotFather
   - `CHAT_ID` = твой telegram id
4. Railway автоматически запустит `worker: python main.py` из Procfile

## 5. Персистентность базы данных

> ⚠️ На Railway бесплатном плане файловая система эфемерная — при перезапуске `planner.db` сбросится.

Чтобы данные сохранялись:
- В Railway добавь **Volume**: Settings → Volumes → Mount path `/data`
- Добавь переменную `DB_PATH=/data/planner.db`

## Проверка

Напиши боту `/start` — должно появиться главное меню.
