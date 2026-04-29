# TG Bot 4based Sender

Telegram-бот для автоматической рассылки сообщений на платформе 4based.
Поддерживает несколько аккаунтов и несколько пользователей одновременно.

---

## Содержание

1. [Локальный запуск (macOS / Windows)](#локальный-запуск-macos--windows)
2. [Деплой на VPS-сервер](#деплой-на-vps-сервер)
3. [Формат файлов](#формат-файлов)
4. [Управление ботом](#управление-ботом)

---

## Локальный запуск (macOS / Windows)

### 1. Требования

- Python **3.11**
- Токен бота от [@BotFather](https://t.me/BotFather)

### 2. Проверить версию Python

```bash
# macOS
python3 --version

# Windows
python --version
```

Если версия не `3.11.x` — скачайте установщик с [python.org](https://www.python.org/downloads/release/python-3110/).
На Windows обязательно поставьте галочку **Add Python to PATH**.

### 3. Создать виртуальное окружение

```bash
# macOS
python3.11 -m venv .venv
source .venv/bin/activate

# Windows
py -3.11 -m venv .venv
.venv\Scripts\activate
```

После активации в начале строки появится `(.venv)`.

### 4. Установить зависимости

```bash
pip install -r requirements.txt
playwright install chromium
```

### 5. Создать файл `.env`

В корне проекта создайте файл `.env`:

```
BOT_TOKEN=ваш_токен_бота
```

### 6. Запустить бота

```bash
# macOS
python3 main.py

# Windows
python main.py
```

---

## Деплой на VPS-сервер

### Рекомендуемые характеристики сервера

| Параметр | Минимум | Рекомендуется |
|----------|---------|---------------|
| RAM      | 2 GB    | 4 GB          |
| CPU      | 2 vCPU  | 2–4 vCPU      |
| Диск     | 20 GB   | 40 GB SSD     |
| ОС       | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

> Каждый запущенный аккаунт открывает отдельный браузер (~300 MB RAM).
> При 5 параллельных аккаунтах нужно минимум 4 GB RAM.

---

### Шаг 1 — Подключиться к серверу

```bash
ssh root@ВАШ_IP_АДРЕС
```

> Если используете ключ: `ssh -i ~/.ssh/id_rsa root@ВАШ_IP_АДРЕС`

---

### Шаг 2 — Обновить систему и установить зависимости ОС

```bash
apt update && apt upgrade -y
apt install -y python3.11 python3.11-venv python3-pip git curl wget unzip \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2
```

> Эти системные библиотеки нужны для работы Chromium (Playwright).

---

### Шаг 3 — Загрузить проект на сервер

**Способ 1 — через Git (рекомендуется):**

```bash
git clone https://github.com/ВАШ_АККАУНТ/TG_bot_4based_sender.git
cd TG_bot_4based_sender
```

**Способ 2 — через SCP (загрузка папки с локального компьютера):**

Выполните на **своём компьютере** (не на сервере):
```bash
scp -r /путь/до/TG_bot_4based_sender root@ВАШ_IP:/root/TG_bot_4based_sender
```

Затем на сервере:
```bash
cd /root/TG_bot_4based_sender
```

---

### Шаг 4 — Создать виртуальное окружение и установить зависимости

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### Шаг 5 — Установить браузер Playwright

```bash
playwright install chromium
playwright install-deps chromium
```

> `install-deps` автоматически доустанавливает недостающие системные библиотеки.

---

### Шаг 6 — Создать файл `.env`

```bash
nano .env
```

Вставьте содержимое:
```
BOT_TOKEN=ваш_токен_бота
```

Сохраните: `Ctrl+O` → `Enter` → `Ctrl+X`.

---

### Шаг 7 — Проверить запуск вручную

```bash
source .venv/bin/activate
python3 main.py
```

Если бот запустился и отвечает в Telegram — всё настроено правильно.
Остановите: `Ctrl+C`.

---

### Шаг 8 — Настроить автозапуск через systemd

Чтобы бот запускался автоматически при старте сервера и перезапускался при падении, создайте службу systemd.

```bash
nano /etc/systemd/system/tgbot.service
```

Вставьте следующий текст (замените путь если проект в другом месте):

```ini
[Unit]
Description=TG Bot 4based Sender
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/TG_bot_4based_sender
ExecStart=/root/TG_bot_4based_sender/.venv/bin/python3 main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Сохраните: `Ctrl+O` → `Enter` → `Ctrl+X`.

Активируйте и запустите службу:

```bash
systemctl daemon-reload
systemctl enable tgbot
systemctl start tgbot
```

Проверьте статус:

```bash
systemctl status tgbot
```

Вы должны увидеть `Active: active (running)`.

---

### Шаг 9 — Обновить бота после изменений в коде

```bash
cd /root/TG_bot_4based_sender

# Если использовали Git:
git pull

# Перезапустить службу:
systemctl restart tgbot
```

---

## Управление ботом

| Действие | Команда |
|----------|---------|
| Запустить | `systemctl start tgbot` |
| Остановить | `systemctl stop tgbot` |
| Перезапустить | `systemctl restart tgbot` |
| Статус | `systemctl status tgbot` |
| Логи в реальном времени | `journalctl -u tgbot -f` |
| Последние 100 строк логов | `journalctl -u tgbot -n 100` |

---

## Формат файлов

### Файл аккаунтов (первый .txt)

Каждая строка — один аккаунт в формате:

```
email:пароль:текст_сообщения:хост:порт:логин_прокси:пароль_прокси
```

Пример:
```
user@example.com:pass123:Привет! Хочу познакомиться:proxy.host.com:8080:proxyuser:proxypass
```

### Файл профилей (второй .txt)

Каждая строка — ссылка на профиль 4based:

```
https://4based.com/username1
https://4based.com/username2
https://4based.com/username3
```

---

## Получение токена бота

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Введите имя бота и username (должен заканчиваться на `bot`)
4. Скопируйте полученный токен в файл `.env`
