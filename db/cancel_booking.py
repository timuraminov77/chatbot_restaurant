import mysql.connector
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from graph.state import BookingState
from config import ADMIN_TG_ID, TELEGRAM_TOKEN
import requests

def _get_conn():
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )


def cancel_booking_node_db(state: BookingState) -> dict:
    print(">>> cancel_booking_node_db вызвана")

    order_id = state.get("cancel_booking_id")

    if not order_id:
        return {
            "should_continue": False,
            "response_text": "Ошибка: не найдена бронь для отмены.",
        }

    conn = _get_conn()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("START TRANSACTION")

        cursor.execute(
            "SELECT * FROM bookings WHERE order_id = %s FOR UPDATE",
            (order_id,)
        )
        booking = cursor.fetchone()

        if not booking:
            conn.rollback()
            conn.close()
            return {
                "should_continue": False,
                "response_text": "Бронь не найдена — возможно, уже была отменена.",
            }

        cursor.execute(
            "DELETE FROM bookings WHERE order_id = %s",
            (order_id,)
        )

        conn.commit()
        conn.close()

        def _notify_admin(text: str):
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": ADMIN_TG_ID, "text": text}
                )
            except Exception as e:
                print(">>> Ошибка уведомления админа:", e)

        _notify_admin(
            f"❌ Бронь отменена!\n"
            f"👤 Telegram ID: {state.get('telegram_id')}\n"
            f"🔖 Номер брони: {order_id}"
        )

        return {
            "should_continue": True,
            "cancel_step": None,
            "response_text": f"Бронь #{order_id} отменена ✅\nБудем рады видеть вас снова!",
        }

    except Exception as e:
        conn.rollback()
        conn.close()
        raise e