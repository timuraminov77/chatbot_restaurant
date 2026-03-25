from datetime import datetime, timedelta
from graph.state import BookingState

SCHEDULE = {
    0: ("12:00", "23:00"),  # Пн
    1: ("12:00", "23:00"),  # Вт
    2: ("12:00", "23:00"),  # Ср
    3: ("12:00", "23:00"),  # Чт
    4: ("12:00", "00:00"),  # Пт
    5: ("11:00", "00:00"),  # Сб
    6: ("11:00", "22:00"),  # Вс
}

LAST_ORDER_OFFSET = 30


def validate_hours_node(state: BookingState) -> dict:
    details = state["booking_details"]
    date_str = details["date"]
    time_str = details["time"]

    dt = datetime.fromisoformat(f"{date_str}T{time_str}:00")
    weekday = dt.weekday()
    open_str, close_str = SCHEDULE[weekday]

    open_h, open_m = map(int, open_str.split(":"))
    close_h, close_m = map(int, close_str.split(":"))

    visit_minutes = dt.hour * 60 + dt.minute
    open_minutes = open_h * 60 + open_m

    if close_h == 0:
        close_minutes = 24 * 60
    else:
        close_minutes = close_h * 60 + close_m

    last_order = close_minutes - LAST_ORDER_OFFSET

    day_names = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
    day_name = day_names[weekday]

    if visit_minutes < open_minutes or visit_minutes >= last_order:
        open_fmt = open_str
        close_fmt = close_str if close_h != 0 else "00:00"
        return {
            "should_continue": False,
            "booking_details": {**details, "date": None, "time": None},
            "response_text": (
                f"В {day_name} ресторан работает с {open_fmt} до {close_fmt} "
                f"(последний заказ в {last_order // 60:02d}:{last_order % 60:02d}).\n"
                f"На какое время вас записать?"
            ),
        }

    now = datetime.now()
    min_time = now + timedelta(hours=2)

    if dt < min_time:
        return {
            "should_continue": False,
            "booking_details": {**details, "date": None, "time": None},
            "response_text": (
                f"Бронь возможна минимум за 2 часа до визита.\n"
                f"На какое время записать?"
            ),
        }

    return {
        "should_continue": True,
        "response_text": None,
    }