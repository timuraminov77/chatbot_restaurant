from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel
from langchain_groq import ChatGroq

from config import GROQ_API_KEY
from graph.state import BookingState
from db.get_bookings import get_user_bookings, format_bookings_list


class SelectBookingResult(BaseModel):
    booking_index: Optional[int] = None  # 1-based индекс из списка


class NewDateTimeResult(BaseModel):
    date: Optional[str] = None
    time: Optional[str] = None


class GuestCountResult(BaseModel):
    guest_count: Optional[int] = None
    confirmed: Optional[bool] = None  # True если клиент подтвердил текущее кол-во


_llm = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.3-70b-versatile", temperature=0)

select_llm = _llm.with_structured_output(SelectBookingResult)
datetime_llm = _llm.with_structured_output(NewDateTimeResult)
guest_llm = _llm.with_structured_output(GuestCountResult)

SELECT_PROMPT = """Пользователь выбирает бронь из списка.
Определи какую бронь он имеет в виду и верни её номер (1, 2, 3...).
Список броней: {bookings_text}

Пользователь может написать:
- номер ("первую", "1", "вторую")
- описание ("завтрашнюю", "вечернюю", "на пятницу", "на 19:00")

Верни booking_index = номер брони (1-based). Если непонятно — верни null."""

DATETIME_PROMPT = """Извлеки из сообщения новую дату и время для переноса брони.
- date: в формате "YYYY-MM-DD". "завтра" → следующий день, "в субботу" → ближайшая суббота.
- time: в формате "HH:MM". Одиночное число от 0 до 23 → часы ("20" = "20:00").
Если поле не упоминалось — верни null.
Сегодня: {today}"""

GUEST_PROMPT = """Пользователю задали вопрос о количестве гостей для переноса брони.
Текущее количество: {current_count} чел.

Определи:
- guest_count: новое число если пользователь назвал другое. null если не назвал.
- confirmed: true если пользователь подтвердил текущее количество (да, верно, столько же, оставить).

Верни guest_count или confirmed."""


def modify_booking_node(state: BookingState) -> dict:
    print(">>> modify_booking_node вызвана, шаг:", state.get("modify_step"))

    telegram_id = state.get("telegram_id")
    step = state.get("modify_step") or "show_list"
    raw_input = state.get("raw_input", "")

    if step == "show_list":
        bookings = get_user_bookings(telegram_id)

        if not bookings:
            return {
                "modify_step": None,
                "should_continue": False,
                "response_text": "У вас нет предстоящих броней 😊",
            }

        if len(bookings) == 1:
            return {
                "user_bookings": bookings,
                "selected_booking": bookings[0],
                "modify_step": "new_datetime",
                "should_continue": False,
                "response_text": _format_single_booking(bookings[0]) + "\nНа какую дату и время перенести?",
            }

        text = format_bookings_list(bookings)
        return {
            "user_bookings": bookings,
            "modify_step": "select",
            "should_continue": False,
            "response_text": text,
        }

    if step == "select":
        bookings = state.get("user_bookings") or []
        bookings_text = format_bookings_list(bookings)

        result = select_llm.invoke([
            {"role": "system", "content": SELECT_PROMPT.format(bookings_text=bookings_text)},
            {"role": "user", "content": raw_input}
        ])

        if not result.booking_index or result.booking_index < 1 or result.booking_index > len(bookings):
            return {
                "modify_step": "select",
                "should_continue": False,
                "response_text": "Не понял какую бронь выбрать. Укажите номер или опишите её.",
            }

        selected = bookings[result.booking_index - 1]
        return {
            "selected_booking": selected,
            "modify_step": "new_datetime",
            "should_continue": False,
            "response_text": f"Переносим {_format_single_booking(selected)}\nНа какую дату и время?",
        }

    if step == "new_datetime":
        today = datetime.now().strftime("%Y-%m-%d")
        result = datetime_llm.invoke([
            {"role": "system", "content": DATETIME_PROMPT.format(today=today)},
            {"role": "user", "content": raw_input}
        ])

        existing = state.get("new_datetime") or {}
        merged = {
            "date": result.date or existing.get("date"),
            "time": result.time or existing.get("time"),
        }

        if not merged["date"]:
            return {
                "new_datetime": merged,
                "modify_step": "new_datetime",
                "should_continue": False,
                "response_text": "На какую дату перенести?",
            }

        if not merged["time"]:
            return {
                "new_datetime": merged,
                "modify_step": "new_datetime",
                "should_continue": False,
                "response_text": "На какое время?",
            }

        selected = state.get("selected_booking") or {}
        current_count = selected.get("count_clients", "?")

        return {
            "new_datetime": merged,
            "modify_step": "confirm_guests",
            "should_continue": False,
            "response_text": f"На {current_count} человек? Или изменилось количество?",
        }

    if step == "confirm_guests":
        selected = state.get("selected_booking") or {}
        current_count = selected.get("count_clients", 2)

        result = guest_llm.invoke([
            {"role": "system", "content": GUEST_PROMPT.format(current_count=current_count)},
            {"role": "user", "content": raw_input}
        ])

        if result.guest_count:
            final_count = result.guest_count
        elif result.confirmed:
            final_count = current_count
        else:
            return {
                "modify_step": "confirm_guests",
                "should_continue": False,
                "response_text": f"Уточните — переносим на {current_count} человек или изменилось?",
            }

        return {
            "new_guest_count": final_count,
            "modify_step": "done",
            "should_continue": True,
            "response_text": None,
        }

    return {
        "should_continue": False,
        "response_text": "Что-то пошло не так, попробуйте снова.",
    }


def _format_single_booking(b: dict) -> str:
    dt = datetime.fromisoformat(b["start_time"])
    return f"📅 {dt.strftime('%d.%m.%Y')} в {dt.strftime('%H:%M')} — 👥 {b['count_clients']} чел."