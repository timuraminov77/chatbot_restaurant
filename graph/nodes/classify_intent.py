from typing import Literal
from pydantic import BaseModel
from langchain_groq import ChatGroq

from config import GROQ_API_KEY
from graph.state import BookingState


class IntentResult(BaseModel):
    intent: Literal["new_booking", "modify_booking", "cancel_booking", "greeting", "unclear"]
    confidence: float


_llm = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.1-8b-instant", temperature=0)
intent_llm = _llm.with_structured_output(IntentResult)

INTENT_SYSTEM_PROMPT = """Ты — ассистент ресторана «У Тимура».
Определи намерение гостя. Верни СТРОГО одно из четырёх значений:

new_booking    — хочет забронировать стол
modify_booking — хочет изменить существующую бронь
cancel_booking — хочет отменить бронь
greeting — приветствие (привет, здравствуйте, добрый день и т.п.)
unclear        — непонятно


ВАЖНО: intent должен быть ТОЛЬКО одним из: new_booking, modify_booking, cancel_booking, unclear.
Никаких других значений.

Отвечай строго по схеме JSON."""


def classify_intent_node(state: BookingState) -> dict:
    print(">>> classify_intent_node вызвана")
    result = intent_llm.invoke([
        {"role": "system", "content": INTENT_SYSTEM_PROMPT},
        {"role": "user",   "content": state["raw_input"]}
    ])

    if result.confidence < 0.7:
        return {"intent": "unclear"}

    if result.intent == "greeting":
        return {
            "intent": "greeting",
            "response_text": "Здравствуйте! 😊 Чем могу помочь? Вы можете забронировать столик или задать вопрос о ресторане."
        }
    return {"intent": result.intent}
