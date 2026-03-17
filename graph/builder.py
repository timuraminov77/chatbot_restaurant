from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import BookingState
from graph.nodes.classify_intent import classify_intent_node
from graph.nodes.extraction import extraction_node
from db.save_booking import save_booking_node


def route_start(state: BookingState) -> str:
    intent = state.get("intent")
    should_continue = state.get("should_continue")

    if intent == "new_booking" and should_continue:
        return "extraction"
    if intent == "new_booking":
        return "extraction"
    if intent == "modify_booking":
        return "modify"
    if intent == "cancel_booking":
        return "cancel"
    return "classify_intent"


def route_intent(state: BookingState) -> str:
    intent = state.get("intent")
    if intent == "new_booking":    return "extraction"
    if intent == "modify_booking": return "modify"
    if intent == "cancel_booking": return "cancel"
    return "ask_intent"


def route_extraction(state: BookingState) -> str:
    if state.get("should_continue"):
        return "done"
    return "wait"


def build_graph():
    builder = StateGraph(BookingState)
    builder.add_node("classify_intent", classify_intent_node)
    builder.add_node("extraction", extraction_node)

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
        "done": END,
        "wait": END,
    })

    memory = MemorySaver()
    return builder.compile(
        checkpointer=memory,
        #interrupt_after=["extraction"]
    )


# Синглтон графа
graph = build_graph()
