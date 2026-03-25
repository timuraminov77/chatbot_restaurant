import mysql.connector
from datetime import datetime, timedelta
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from graph.state import BookingState

import requests
from config import ADMIN_TG_ID, TELEGRAM_TOKEN

def _get_conn():
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )


def modify_booking_node_db(state: BookingState) -> dict:
    print(">>> modify_booking_node_db вызвана")

    selected = state.get("selected_booking") or {}
    new_dt = state.get("new_datetime") or {}
    new_guest_count = state.get("new_guest_count")
    old_order_id = selected.get("order_id")

    date_time = f"{new_dt['date']}T{new_dt['time']}:00"
    duration_hours = 2
    end_time = (datetime.fromisoformat(date_time) + timedelta(hours=duration_hours)).isoformat()
    guest_count = new_guest_count or selected.get("count_clients")

    conn = _get_conn()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("START TRANSACTION")

        cursor.execute("""
            SELECT id FROM tables
            WHERE capacity >= %s
              AND capacity <= %s
              AND id NOT IN (
                  SELECT table_id FROM bookings
                  WHERE start_time < %s AND end_time > %s
                  AND order_id != %s
              )
            ORDER BY capacity ASC
            LIMIT 1
            FOR UPDATE
        """, (guest_count, guest_count + 2, end_time, date_time, old_order_id))

        table = cursor.fetchone()

        if not table:
            conn.rollback()
            conn.close()
            return {
                "should_continue": False,
                "modify_step": "new_datetime",
                "new_datetime": {"date": None, "time": None},
                "response_text": "К сожалению, на это время подходящих столов нет 😔\nПопробуйте другое — на какую дату и время?",
            }

        table_id = table["id"]

        dt = datetime.fromisoformat(date_time)
        weekday = dt.weekday()
        from graph.nodes.validate_hours import SCHEDULE, LAST_ORDER_OFFSET
        open_str, close_str = SCHEDULE[weekday]
        open_h, open_m = map(int, open_str.split(":"))
        close_h, close_m = map(int, close_str.split(":"))
        visit_minutes = dt.hour * 60 + dt.minute
        open_minutes = open_h * 60 + open_m
        close_minutes = 24 * 60 if close_h == 0 else close_h * 60 + close_m
        last_order = close_minutes - LAST_ORDER_OFFSET

        if visit_minutes < open_minutes or visit_minutes >= last_order:
            conn.rollback()
            conn.close()
            day_names = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
            return {
                "should_continue": False,
                "modify_step": "new_datetime",
                "new_datetime": {"date": None, "time": None},
                "response_text": (
                    f"В {day_names[weekday]} ресторан работает с {open_str} до {close_str}.\n"
                    f"На какое время перенести?"
                ),
            }

        cursor.execute(
            "SELECT user_id FROM bookings WHERE order_id = %s",
            (old_order_id,)
        )
        row = cursor.fetchone()
        user_id = row["user_id"]

        cursor.execute(
            "DELETE FROM bookings WHERE order_id = %s",
            (old_order_id,)
        )

        cursor.execute("""
            INSERT INTO bookings
                (user_id, table_id, start_time, end_time, count_clients)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, table_id, date_time, end_time, guest_count))

        new_order_id = cursor.lastrowid
        conn.commit()
        conn.close()

        dt_fmt = datetime.fromisoformat(date_time)

        def _notify_admin(text: str):
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": ADMIN_TG_ID, "text": text}
                )
            except Exception as e:
                print(">>> Ошибка уведомления админа:", e)

        _notify_admin(
            f"🆕 Бронь перенесена!\n"
            f"👤 Telegram ID: {state.get('telegram_id')}\n"
            f"📅 {dt_fmt.strftime('%d.%m.%Y')} в {dt_fmt.strftime('%H:%M')}\n"
            f"👥 Гостей: {new_guest_count}\n"
            f"🔖 Номер брони: {new_order_id}"
        )

        return {
            "should_continue": True,
            "modify_step": None,
            "response_text": (
                f"Бронь перенесена! 🎉\n"
                f"📅 {dt_fmt.strftime('%d.%m.%Y')} в {dt_fmt.strftime('%H:%M')}\n"
                f"👥 Гостей: {guest_count}\n"
                f"🔖 Новый номер брони: {new_order_id}"
            ),
        }

    except Exception as e:
        conn.rollback()
        conn.close()
        raise e