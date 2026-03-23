import mysql.connector
from datetime import datetime, timedelta
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from graph.state import BookingState


def _get_conn():
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )


def check_table_node(state: BookingState) -> dict:
    details = state["booking_details"]
    guest_count = details["guest_count"]
    date_time = f"{details['date']}T{details['time']}:00"
    duration_hours = details.get("duration") or 2
    end_time = (datetime.fromisoformat(date_time) + timedelta(hours=duration_hours)).isoformat()

    conn = _get_conn()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, capacity FROM tables
        WHERE capacity >= %s
          AND capacity <= %s
          AND id NOT IN (
              SELECT table_id FROM bookings
              WHERE start_time < %s AND end_time > %s
          )
        ORDER BY capacity ASC
    """, (guest_count, guest_count + 2, end_time, date_time))

    tables = cursor.fetchall()
    conn.close()

    if not tables:
        return {
            "available_tables": [],
            "should_continue": False,
            "booking_details": {**details, "date": None, "time": None},
            "response_text": "К сожалению, на это время подходящих столов нет 😔\nПопробуйте другое — на какую дату и время?",
        }

    print(f">>> выбран стол id={tables[0]['id']} capacity={tables[0]['capacity']} для {guest_count} гостей")

    return {
        "available_tables": tables,
        "should_continue": True,
        "response_text": None,
    }