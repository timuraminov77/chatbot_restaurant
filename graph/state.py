from typing import Optional
from langgraph.graph import MessagesState


class BookingState(MessagesState):
    raw_input: str
    intent: Optional[str]
    booking_details: Optional[dict]
    should_continue: bool
    response_text: Optional[str]
    telegram_id: Optional[int]
    cancel_flow: bool
    available_tables: Optional[list]
    extraction_stage: int

    # ветка modify
    modify_step: Optional[str]
    user_bookings: Optional[list]
    selected_booking: Optional[dict]
    new_datetime: Optional[dict]
    new_guest_count: Optional[int]