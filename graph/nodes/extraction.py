from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from langchain_groq import ChatGroq

from config import GROQ_API_KEY
from graph.state import BookingState
import re

class BookingDetails(BaseModel):
    date: Optional[str] = None
    time: Optional[str] = None
    guest_count: Optional[int] = None
    phone: Optional[str] = None
    name: Optional[str] = None


MISSING_QUESTIONS = {
    "дата":              "На какую дату планируете визит?",
    "время":             "На какое время?",
    "количество гостей": "Сколько человек будет?",
    "номер телефона":    "Ваш номер телефона для подтверждения?",
    "имя":               "Как вас зовут?",
}

extraction_llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.3-70b-versatile",
    temperature=0
).with_structured_output(BookingDetails)

EXTRACTION_SYSTEM_PROMPT = """Ты — ассистент ресторана «У Тимура».

Извлеки из истории диалога пять полей:
- date: дата визита в формате "YYYY-MM-DD". "завтра" → следующий день от сегодня, "в субботу" → ближайшая суббота.
- time: время визита в формате "HH:MM". Только если пользователь явно назвал время.
- guest_count: количество гостей (целое число > 0)
- phone: номер телефона — любая строка из цифр длиной от 5 символов
- name: имя гостя — только слова, не цифры

ВАЖНО: не додумывай значения. Только то, что явно сказал пользователь.
Если поле не упоминалось — верни null.
Сегодня: {today}"""


def extraction_node(state: BookingState) -> dict:
    print(">>> extraction_node вызвана")
    today = datetime.now().strftime("%Y-%m-%d")

    result: BookingDetails = extraction_llm.invoke([
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT.format(today=today)},
        *state["messages"]
    ])

    new_details = result.model_dump()
    old_details = state.get("booking_details") or {}

    merged = {
        key: old_details.get(key) or new_details.get(key)
        for key in new_details
    }

    if merged.get("phone"):
        digits = re.sub(r'\D', '', new_details["phone"])
        if len(digits) != 11:
            MISSING_QUESTIONS["номер телефона"] = "Введите корректный номер в формате 89XXXXXXXXX"
            merged["phone"] = None
        else:
            merged["phone"] = digits

    missing = []
    if not merged.get("date"):         missing.append("дата")
    if not merged.get("time"):         missing.append("время")
    if not merged.get("guest_count"):  missing.append("количество гостей")
    if not merged.get("phone"):        missing.append("номер телефона")
    if not merged.get("name"):         missing.append("имя")

    print(">>> missing:", missing)

    if not missing:
        return {
            "booking_details": merged,
            "should_continue": True,
            "response_text": None
        }

    question_text = MISSING_QUESTIONS[missing[0]]

    return {
        "booking_details": merged,
        "should_continue": False,
        "response_text": question_text
    }