from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from langchain_groq import ChatGroq

from config import GROQ_API_KEY
from graph.state import BookingState
from db.get_bookings import get_user_bookings, format_bookings_list


class SelectBookingResult(BaseModel):
    booking_index: Optional[int] = None


class ConfirmResult(BaseModel):
    confirmed: Optional[bool] = None


_llm = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.1-8b-instant", temperature=0)

select_llm = _llm.with_structured_output(SelectBookingResult)
confirm_llm = _llm.with_structured_output(ConfirmResult)

SELECT_PROMPT = SELECT_PROMPT = """Пользователь выбирает бронь для отмены из списка.
Список броней:
{bookings_text}

Правила:
- "первую", "1", "первая" → booking_index = 1
- "вторую", "2", "вторая" → booking_index = 2
- "вечернюю", "позднюю", "последнюю" → выбери с наибольшим временем
- "утреннюю", "раннюю", "первую по времени" → выбери с наименьшим временем
- "на 5 вечера", "в 17", "17:00" → найди бронь с ближайшим временем к 17:00
- "на 14", "в 14:00", "дневную" → найди бронь с ближайшим временем к 14:00

Верни booking_index = номер брони (1-based). Если совсем непонятно — верни null."""

CONFIRM_PROMPT = """Пользователю задали вопрос — подтверждает ли он отмену брони.
Верни confirmed=true если да (да, подтверждаю, отменить, верно, точно).
Верни confirmed=false если нет (нет, не надо, отказываюсь, передумал)."""


def cancel_booking_node(state: BookingState) -> dict:
    print(">>> cancel_booking_node вызвана, шаг:", state.get("cancel_step"))

    telegram_id = state.get("telegram_id")
    step = state.get("cancel_step") or "show_list"
    raw_input = state.get("raw_input", "")

    if step == "show_list":
        bookings = get_user_bookings(telegram_id)

        if not bookings:
            return {
                "cancel_step": None,
                "should_continue": False,
                "response_text": "У вас нет предстоящих броней 😊",
            }

        if len(bookings) == 1:
            b = bookings[0]
            dt = datetime.fromisoformat(b["start_time"])
            return {
                "user_bookings": bookings,
                "cancel_booking_id": b["order_id"],
                "cancel_step": "confirm",
                "should_continue": False,
                "response_text": (
                    f"Найдена бронь:\n"
                    f"📅 {dt.strftime('%d.%m.%Y')} в {dt.strftime('%H:%M')} — "
                    f"👥 {b['count_clients']} чел.\n\n"
                    f"Подтверждаете отмену?"
                ),
            }

        text = format_bookings_list(bookings)
        text = text.replace("Какую бронь хотите перенести?", "Какую бронь хотите отменить?")
        return {
            "user_bookings": bookings,
            "cancel_step": "select",
            "should_continue": False,
            "response_text": text,
        }

    if step == "select":
        bookings = state.get("user_bookings") or []
        bookings_text = format_bookings_list(bookings)
        bookings_text = bookings_text.replace("Какую бронь хотите перенести?", "Какую бронь хотите отменить?")

        result = select_llm.invoke([
            {"role": "system", "content": SELECT_PROMPT.format(bookings_text=bookings_text)},
            {"role": "user", "content": raw_input}
        ])

        print(">>> select result:", result)

        if not result.booking_index or result.booking_index < 1 or result.booking_index > len(bookings):
            return {
                "cancel_step": "select",
                "should_continue": False,
                "response_text": "Не понял какую бронь отменить. Укажите номер или опишите её.",
            }

        b = bookings[result.booking_index - 1]
        dt = datetime.fromisoformat(b["start_time"])
        return {
            "cancel_booking_id": b["order_id"],
            "cancel_step": "confirm",
            "should_continue": False,
            "response_text": (
                f"Отменяем бронь:\n"
                f"📅 {dt.strftime('%d.%m.%Y')} в {dt.strftime('%H:%M')} — "
                f"👥 {b['count_clients']} чел.\n\n"
                f"Подтверждаете отмену?"
            ),
        }

    if step == "confirm":
        result = confirm_llm.invoke([
            {"role": "system", "content": CONFIRM_PROMPT},
            {"role": "user", "content": raw_input}
        ])

        if result.confirmed is None:
            return {
                "cancel_step": "confirm",
                "should_continue": False,
                "response_text": "Подтверждаете отмену брони? (да / нет)",
            }

        if not result.confirmed:
            return {
                "cancel_step": None,
                "should_continue": False,
                "response_text": "Хорошо, бронь сохранена 😊",
            }

        return {
            "cancel_step": "done",
            "should_continue": True,
            "response_text": None,
        }

    return {
        "should_continue": False,
        "response_text": "Что-то пошло не так, попробуйте снова.",
    }