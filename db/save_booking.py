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
    date_time = f"{details['date']}T{details['time']}:00"
    duration_hours = details.get("duration") or 2
    end_time = (datetime.fromisoformat(date_time) + timedelta(hours=duration_hours)).isoformat()

    tables = state.get("available_tables") or []
    table = tables[0] if tables else None

    if not table:
        return {
            "response_text": "Ошибка выбора стола, попробуйте снова.",
            "should_continue": False
        }

    table_id = table["id"]
    conn = _get_conn()
    cursor = conn.cursor()

    try:
        cursor.execute("START TRANSACTION")

        cursor.execute("SELECT id FROM tables WHERE id = %s FOR UPDATE", (table_id,))
        cursor.fetchall()  # читаем результат

        cursor.execute("""
            SELECT COUNT(*) FROM bookings
            WHERE table_id = %s
              AND start_time < %s
              AND end_time > %s
        """, (table_id, end_time, date_time))

        count = cursor.fetchone()[0]

        if count > 0:
            conn.rollback()
            conn.close()
            return {
                "response_text": "К сожалению, этот стол только что заняли 😔\nПопробуйте другое время — на какое?",
                "should_continue": False,
                "booking_details": {**details, "date": None, "time": None},
                "available_tables": [],
            }

        cursor.execute("""
            INSERT INTO users (telegram_id, name, phone)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE name=%s, phone=%s
        """, (
            state.get("telegram_id", 0),
            details["name"], details["phone"],
            details["name"], details["phone"]
        ))

        cursor.execute(
            "SELECT id FROM users WHERE telegram_id=%s",
            (state.get("telegram_id", 0),)
        )
        user_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO bookings
                (user_id, table_id, start_time, end_time, count_clients)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, table_id, date_time, end_time, details["guest_count"]))

        booking_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            "response_text": (
                f"Бронь подтверждена! 🎉\n"
                f"📅 {details['date']} в {details['time']}\n"
                f"👥 Гостей: {details['guest_count']}\n"
                f"🔖 Номер брони: {booking_id}"
            ),
            "should_continue": True
        }

    except Exception as e:
        conn.rollback()
        conn.close()
        raise e