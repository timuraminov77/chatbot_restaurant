# admin_agent.py
import json
import requests
import mysql.connector
from datetime import date

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY

from config import (
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
    TELEGRAM_TOKEN, GROQ_API_KEY
)

_llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o-mini", temperature=0)

def _get_conn():
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )

# ── инструменты ──────────────────────────────────────────────

@tool
def query_database(sql: str) -> str:

    """Выполняет SELECT-запрос к БД ресторана.
    Таблицы: bookings(order_id, user_id, table_id, start_time, end_time, count_clients),
    users(id, telegram_id, name, phone), tables(id, capacity)."""

    print("Вызван query_database")
    if not sql.strip().lower().startswith("select"):
        return "Ошибка: только SELECT запросы разрешены"
    try:
        conn = _get_conn()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
        return json.dumps({"rows": rows, "count": len(rows)}, ensure_ascii=False)
    except Exception as e:
        return f"Ошибка БД: {e}"

@tool
def get_today_bookings() -> str:
    """Возвращает все брони на сегодня с именем, телефоном и telegram_id гостей."""
    print("Вызван get_today_bookings")
    today = date.today().isoformat()
    sql = f"""SELECT b.order_id, b.start_time, b.end_time, b.count_clients,
               u.name, u.phone, u.telegram_id
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE DATE(b.start_time) = '{today}'
        ORDER BY b.start_time ASC""".strip()
    return query_database.invoke(sql)

@tool
def send_telegram(telegram_id: int, text: str) -> str:
    """Отправляет сообщение гостю в Telegram по его telegram_id."""
    print("Вызван send_telegram")
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": telegram_id, "text": text}
        )
        ok = r.json().get("ok")
        return f"Отправлено: {ok} → {telegram_id}"
    except Exception as e:
        return f"Ошибка отправки: {e}"

# ── агент ────────────────────────────────────────────────────

SYSTEM = f"""Ты — ИИ-ассистент администратора ресторана «У Тимура».
Умеешь делать запросы к БД и рассылать сообщения гостям в Telegram.
Сегодня: {date.today().isoformat()}.
Отвечай кратко.

ВАЖНО:
- Для броней на сегодня используй get_today_bookings
- Для броней на другую дату используй query_database с нужной датой
- ВСЕГДА сначала вызывай инструмент, потом отвечай. Никогда не отвечай без вызова инструмента.
- Таблицы: bookings(order_id, user_id, table_id, start_time, end_time, count_clients), users(id, telegram_id, name, phone)
"""

_agent = create_react_agent(
    model=_llm,
    tools=[query_database, get_today_bookings, send_telegram],
    prompt=SYSTEM,
)

def run_admin_agent(user_message: str, history: list) -> tuple[str, list]:
    messages = history + [{"role": "user", "content": user_message}]
    result = _agent.invoke({"messages": messages})
    all_messages = result["messages"]
    for m in all_messages:
        print(">>>", type(m).__name__, ":", m.content[:200] if m.content else "")
    reply = all_messages[-1].content
    return reply, all_messages