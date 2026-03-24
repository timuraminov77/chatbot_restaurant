from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import BookingState
from graph.nodes.classify_intent import classify_intent_node
from graph.nodes.extraction import extraction_node
from db.check_table import check_table_node
from db.save_booking import save_booking_node
from graph.nodes.validate_hours import validate_hours_node

def route_start(state: BookingState) -> str:
    intent = state.get("intent")
    if intent == "new_booking":    return "extraction"
    if intent == "modify_booking": return "modify"
    if intent == "cancel_booking": return "cancel"
    return "classify_intent"


def route_intent(state: BookingState) -> str:
    intent = state.get("intent")
    if intent == "new_booking":    return "extraction"
    if intent == "modify_booking": return "modify"
    if intent == "cancel_booking": return "cancel"
    return "ask_intent"


def route_extraction(state: BookingState) -> str:
    if state.get("cancel_flow"):     return "cancelled"
    if state.get("should_continue"):
        if state.get("extraction_stage") == 2:
            return "save"
        return "validate_hours"
    return "wait"

def route_validate_hours(state: BookingState) -> str:
    if state.get("should_continue"): return "check_table"
    return "wait"

def route_check_table(state: BookingState) -> str:
    if state.get("should_continue"): return "extraction"
    return "wait"


def build_graph():
    builder = StateGraph(BookingState)
    builder.add_node("classify_intent", classify_intent_node)
    builder.add_node("extraction", extraction_node)
    builder.add_node("check_table", check_table_node)
    builder.add_node("save", save_booking_node)
    builder.add_node("validate_hours", validate_hours_node)

    builder.add_conditional_edges(START, route_start, {
        "classify_intent": "classify_intent",
        "extraction":      "extraction",
        "modify":          END,
        "cancel":          END,
    })
    builder.add_conditional_edges("classify_intent", route_intent, {
        "extraction": "extraction",
        "ask_intent": END,
        "modify":     END,
        "cancel":     END,
    })
    builder.add_conditional_edges("extraction", route_extraction, {
        "validate_hours": "validate_hours",
        "save":        "save",
        "cancelled":   END,
        "wait":        END,
    })
    builder.add_conditional_edges("validate_hours", route_validate_hours, {
        "check_table": "check_table",
        "wait": END,
    })
    builder.add_conditional_edges("check_table", route_check_table, {
        "extraction": "extraction",
        "wait":       END,
    })
    builder.add_edge("save", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


graph = build_graph()