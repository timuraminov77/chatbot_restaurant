import uuid
from datetime import datetime, timedelta
import mysql.connector

from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from graph.state import BookingState


def _get_conn():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def save_booking_node(state: BookingState) -> dict:
    print(">>> save_booking_node вызвана")

    details = state["booking_details"]

    # Собираем date_time из отдельных полей
    date_str = details.get("date")
    time_str = details.get("time")
    date_time = f"{date_str}T{time_str}:00"

    conn = _get_conn()
    cursor = conn.cursor()

    # Upsert пользователя
    cursor.execute("""
        INSERT INTO users (telegram_id, full_name, phone)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE full_name=%s, phone=%s
    """, (
        state.get("telegram_id", 0),
        details["name"],
        details["phone"],
        details["name"],
        details["phone"]
    ))

    cursor.execute(
        "SELECT id FROM users WHERE telegram_id=%s",
        (state.get("telegram_id", 0),)
    )
    user_id = cursor.fetchone()[0]

    # Ищем свободный стол
    cursor.execute("""
        SELECT id FROM restaurant.tables
        WHERE is_active = 1
          AND id NOT IN (
              SELECT table_id FROM bookings
              WHERE status IN ('pending','confirmed','arrived')
                AND start_time < %s
                AND end_time > %s
          )
        LIMIT 1
    """, (date_time, date_time))

    table = cursor.fetchone()
    if not table:
        conn.close()
        return {
            "response_text": "К сожалению, на это время свободных столов нет.",
            "should_continue": False
        }

    table_id = table[0]

    # Создаём бронь
    booking_id = str(uuid.uuid4())
    end_time_dt = datetime.fromisoformat(date_time) + timedelta(hours=2)
    end_time = end_time_dt.isoformat()

    cursor.execute("""
        INSERT INTO bookings
            (id, user_id, table_id, start_time, end_time, guest_count, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'confirmed')
    """, (booking_id, user_id, table_id, date_time, end_time, details["guest_count"]))

    conn.commit()
    conn.close()

    return {
        "response_text": (
            f"Бронь подтверждена! 🎉\n"
            f"📅 {details['date']} в {details['time']}\n"
            f"👥 Гостей: {details['guest_count']}\n"
            f"🔖 Номер брони: {booking_id[:8].upper()}"
        ),
        "should_continue": True
    }
