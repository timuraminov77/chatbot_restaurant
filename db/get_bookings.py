import mysql.connector
from datetime import datetime
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


def _get_conn():
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )


def get_user_bookings(telegram_id: int) -> list:
    """Возвращает все будущие брони пользователя по telegram_id."""
    conn = _get_conn()
    cursor = conn.cursor(dictionary=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT 
            b.order_id,
            b.start_time,
            b.end_time,
            b.count_clients,
            b.table_id
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE u.telegram_id = %s
          AND b.start_time > %s
        ORDER BY b.start_time ASC
    """, (telegram_id, now))

    bookings = cursor.fetchall()
    conn.close()

    for b in bookings:
        b["start_time"] = b["start_time"].strftime("%Y-%m-%d %H:%M:%S")
        b["end_time"] = b["end_time"].strftime("%Y-%m-%d %H:%M:%S")

    return bookings


def format_bookings_list(bookings: list) -> str:
    """Форматирует список броней для вывода пользователю."""
    if not bookings:
        return None

    lines = ["Ваши предстоящие брони:\n"]
    for i, b in enumerate(bookings, 1):
        dt = datetime.fromisoformat(b["start_time"])
        date_str = dt.strftime("%d.%m.%Y")
        time_str = dt.strftime("%H:%M")
        lines.append(f"{i}. 📅 {date_str} в {time_str} — 👥 {b['count_clients']} чел.")

    lines.append("\nКакую бронь хотите перенести?")
    return "\n".join(lines)