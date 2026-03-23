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
    duration: Optional[int] = None

class CancelFlowResult(BaseModel):
    wants_to_cancel: bool

MISSING_QUESTIONS = {
    "дата":              "На какую дату планируете визит?",
    "время":             "На какое время?",
    "количество гостей": "Сколько человек будет?",
    "номер телефона":    "Ваш номер телефона для подтверждения?",
    "имя":               "Как вас зовут?",
}

CANCEL_FLOW_PROMPT = """Ты определяешь, хочет ли пользователь прервать процесс бронирования.
Верни wants_to_cancel: true если пользователь написал что-то вроде:
«передумал», «не надо», «отмена», «стоп», «не хочу», «выйти», «назад», «забудь»
Верни wants_to_cancel: false если это просто ответ на вопрос (дата, время, имя, телефон)."""

cancel_flow_llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.3-70b-versatile",
    temperature=0
).with_structured_output(CancelFlowResult)

extraction_llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.3-70b-versatile",
    temperature=0
).with_structured_output(BookingDetails)

EXTRACTION_SYSTEM_PROMPT = """Ты — ассистент ресторана «У Тимура».

Извлеки из истории диалога пять полей:
- date: дата визита в формате "YYYY-MM-DD". "завтра" → следующий день от сегодня, "в субботу" → ближайшая суббота.
- time: время визита в формате "HH:MM". Только если пользователь явно назвал время.
- guest_count: количество гостей (целое число > 0). только явно названное число гостей. "ещё стол", "снова", "тоже" — не считать как количество.
- phone: номер телефона — любая строка из цифр длиной от 5 символов
- duration: количество часов если клиент явно сказал ("на 3 часа", "до 22:00" → считай разницу с time). Иначе null.
- name: имя гостя — только слова, не цифры

ВАЖНО: не додумывай значения. Только то, что явно сказал пользователь.
Если поле не упоминалось — верни null.
Сегодня: {today}"""


def extraction_node(state: BookingState) -> dict:
    print(">>> extraction_node вызвана")


    cancel_check = cancel_flow_llm.invoke([
        {"role": "system", "content": CANCEL_FLOW_PROMPT},
        {"role": "user", "content": state["raw_input"]}
    ])
    if cancel_check.wants_to_cancel:
        return {
            "cancel_flow": True,
            "should_continue": False,
            "response_text": "Будем рады Вас видеть, когда снова надумаете забронировать стол😊",
        }

    old_available = state.get("available_tables")
    reset_tables = old_available == []

    today = datetime.now().strftime("%Y-%m-%d")

    result: BookingDetails = extraction_llm.invoke([
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT.format(today=today)},
        *state["messages"]
    ])

    new_details = result.model_dump()
    old_details = state.get("booking_details") or {}

    merged = {
        key: new_details.get(key) or old_details.get(key)
        for key in new_details
    }

    if merged.get("phone"):
        digits = re.sub(r'\D', '', new_details["phone"])
        if len(digits) != 11:
            merged["phone"] = None
        else:
            merged["phone"] = digits

    missing_stage1 = []
    if not merged.get("date"):        missing_stage1.append("дата")
    if not merged.get("time"):        missing_stage1.append("время")
    if not merged.get("guest_count"): missing_stage1.append("количество гостей")

    if missing_stage1:
        return {
            "booking_details": merged,
            "should_continue": False,
            "cancel_flow": False,
            "response_text": MISSING_QUESTIONS[missing_stage1[0]],
        }

    if state.get("available_tables") is None or reset_tables:
        return {
            "booking_details": merged,
            "should_continue": True,
            "cancel_flow": False,
            "extraction_stage": 1,
            "response_text": None,
        }

    missing_stage2 = []
    if not merged.get("phone"): missing_stage2.append("номер телефона")
    if not merged.get("name"):  missing_stage2.append("имя")

    if missing_stage2:
        if missing_stage2[0] == "номер телефона" and new_details.get("phone") is not None:
            question_text = "Введите корректный номер в формате 89XXXXXXXXX"
        else:
            question_text = MISSING_QUESTIONS[missing_stage2[0]]
        return {
            "booking_details": merged,
            "should_continue": False,
            "cancel_flow": False,
            "response_text": question_text,
        }

    return {
        "booking_details": merged,
        "should_continue": True,
        "cancel_flow": False,
        "extraction_stage": 2,
        "response_text": None,
    }