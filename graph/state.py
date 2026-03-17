from typing import Optional
from langgraph.graph import MessagesState


class BookingState(MessagesState):
    raw_input: str
    intent: Optional[str]
    booking_details: Optional[dict]
    should_continue: bool
    response_text: Optional[str]
    telegram_id: Optional[int]
