from langgraph.graph import StateGraph, START, END
from langchain_core.messages import ToolMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from typing import Callable

from src.utilities import State, Assistant, create_tool_node_with_fallback
from src.tools.lookup_policies_retriever_tool import lookup_policy
from src.assistant.primary_assistant import primary_assistant_runnable

from src.assistant.flight_assistant import flight_runnable
from src.tools.flights import (fetch_user_flight_information, search_flights, cancel_ticket,
                                       update_ticket_to_new_flight)

from src.assistant.hotel_assistant import book_hotel_runnable
from src.tools.hotels import book_hotel, update_hotel, cancel_hotel, search_hotels

from src.assistant.car_rental_assistant import car_rental_runnable
from src.tools.car_rental import book_car_rental, search_car_rentals, cancel_car_rental, update_car_rental

from src.assistant.excursion_assistant import book_excursion_runnable
from src.tools.excursions import (book_excursion, update_excursion, cancel_excursion,
                                          search_trip_recommendations)
from src.edges import (route_book_hotel, route_book_excursion, route_to_workflow, route_book_car_rental,
                               route_update_flight, route_primary_assistant)

def user_info(state: State):
    return {"user_info": fetch_user_flight_information.invoke({})}


def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    def entry_node(state: State) -> dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    content=f"The assistant is now the {assistant_name}. "
                            f"Reflect on the above conversation between the host assistant and the user. "
                            f"The user's intent is unsatisfied. Use the provided tools to assist the user. "
                            f"Remember, you are {assistant_name}, and the booking, update, "
                            f"other action is not complete until after you have successfully invoked "
                            f"the appropriate tool. If the user changes their mind or needs help for other tasks, "
                            f"call the CompleteOrEscalate function to let the primary host assistant take control. "
                            f"Do not mention who you are - just act as the proxy for the assistant.",
                    tool_call_id=tool_call_id,
                    name=assistant_name
                )
            ],
            "dialog_state": new_dialog_state,
        }

    return entry_node



# This node will be shared for exiting all specialized assistants
def pop_dialog_state(state: State) -> dict:
    """Pop the dialog stack and return to the main assistant.

    This lets the full graph explicitly track the dialog flow and delegate control
    to specific sub-graphs.
    """
    messages = []
    if state["messages"][-1].tool_calls:
        # Note: Doesn't currently handle the edge case where the llm performs parallel tool calls
        messages.append(
            ToolMessage(
                content="Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed.",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
                nmae=state["messages"][-1].tool_calls[0]["name"]
            )
        )
    return {
        "dialog_state": "pop",
        "messages": messages,
    }


def creat_workflow_graph():

    workflow = StateGraph(state_schema=State)

    workflow.add_node("fetch_user_info", user_info)

    # Primary assistant
    workflow.add_node("primary_assistant", Assistant(primary_assistant_runnable()))

    primary_assistant_tools = [TavilySearchResults(max_results=1), search_flights, lookup_policy]

    workflow.add_node(
        "primary_assistant_tools", create_tool_node_with_fallback(primary_assistant_tools)
    )

    # Flight booking assistant
    workflow.add_node(
        "enter_update_flight",
        create_entry_node("Flight Updates & Booking Assistant", "update_flight"),
    )

    workflow.add_node("update_flight", Assistant(flight_runnable()))
    update_flight_sensitive_tools = [cancel_ticket, update_ticket_to_new_flight]
    workflow.add_node(
        "update_flight_sensitive_tools",
        create_tool_node_with_fallback(update_flight_sensitive_tools),
    )
    update_flight_safe_tools = [search_flights]
    workflow.add_node(
        "update_flight_safe_tools",
        create_tool_node_with_fallback(update_flight_safe_tools),
    )

    # Car rental assistant

    workflow.add_node(
        "enter_book_car_rental",
        create_entry_node(assistant_name="Car Rental Assistant", new_dialog_state="book_car_rental"),
    )
    workflow.add_node("book_car_rental", Assistant(car_rental_runnable()))

    book_car_rental_safe_tools = [search_car_rentals]
    workflow.add_node(
        "book_car_rental_safe_tools",
        create_tool_node_with_fallback(book_car_rental_safe_tools),
    )
    book_car_rental_sensitive_tools = [
        book_car_rental,
        update_car_rental,
        cancel_car_rental,
    ]

    workflow.add_node(
        "book_car_rental_sensitive_tools",
        create_tool_node_with_fallback(book_car_rental_sensitive_tools),
    )

    # Hotel booking assistant
    workflow.add_node(
        "enter_book_hotel", create_entry_node(assistant_name="Hotel Booking Assistant", new_dialog_state="book_hotel")
    )

    workflow.add_node("book_hotel", Assistant(book_hotel_runnable()))

    book_hotel_safe_tools = [search_hotels]
    workflow.add_node(
        "book_hotel_safe_tools",
        create_tool_node_with_fallback(book_hotel_safe_tools),
    )

    book_hotel_sensitive_tools = [book_hotel, update_hotel, cancel_hotel]
    workflow.add_node(
        "book_hotel_sensitive_tools",
        create_tool_node_with_fallback(book_hotel_sensitive_tools),
    )

    # Excursion assistant
    workflow.add_node(
        "enter_book_excursion",
        create_entry_node(assistant_name="Trip Recommendation Assistant", new_dialog_state="book_excursion"),
    )

    workflow.add_node("book_excursion", Assistant(book_excursion_runnable()))

    book_excursion_safe_tools = [search_trip_recommendations]
    workflow.add_node(
        "book_excursion_safe_tools",
        create_tool_node_with_fallback(book_excursion_safe_tools),
    )

    book_excursion_sensitive_tools = [book_excursion, update_excursion, cancel_excursion]
    workflow.add_node(
        "book_excursion_sensitive_tools",
        create_tool_node_with_fallback(book_excursion_sensitive_tools),
    )
    workflow.add_node("leave_skill", pop_dialog_state)

    # Start Adding Edges
    workflow.add_edge(START, "fetch_user_info")

    workflow.add_conditional_edges(source="fetch_user_info", path=route_to_workflow,
                                  path_map={"primary_assistant": "primary_assistant", "update_flight": "update_flight",
                                            "book_car_rental": "book_car_rental", "book_hotel": "book_hotel",
                                            "book_excursion": "book_excursion"})

    # The assistant can route to one of the delegated assistants,
    # directly use a tool, or directly respond to the user
    workflow.add_conditional_edges(source="primary_assistant", path=route_primary_assistant,
                                  path_map={"enter_update_flight": "enter_update_flight",
                                            "enter_book_car_rental": "enter_book_car_rental",
                                            "enter_book_hotel": "enter_book_hotel",
                                            "enter_book_excursion": "enter_book_excursion",
                                            "primary_assistant_tools": "primary_assistant_tools",
                                            "END": END}
                                  )
    workflow.add_edge("primary_assistant_tools", "primary_assistant")
    workflow.add_edge("enter_update_flight", "update_flight")

    workflow.add_edge("update_flight_sensitive_tools", "update_flight")
    workflow.add_edge("update_flight_safe_tools", "update_flight")
    workflow.add_conditional_edges(source="update_flight", path=route_update_flight,
                                  path_map={"update_flight_sensitive_tools": "update_flight_sensitive_tools",
                                            "update_flight_safe_tools": "update_flight_safe_tools",
                                            "leave_skill": "leave_skill", "END": END}
                                  )
    workflow.add_edge("leave_skill", "primary_assistant")
    workflow.add_edge("enter_book_car_rental", "book_car_rental")

    workflow.add_edge("book_car_rental_sensitive_tools", "book_car_rental")
    workflow.add_edge("book_car_rental_safe_tools", "book_car_rental")
    workflow.add_conditional_edges(source="book_car_rental", path=route_book_car_rental,
                                  path_map={"book_car_rental_safe_tools": "book_car_rental_safe_tools",
                                            "book_car_rental_sensitive_tools": "book_car_rental_sensitive_tools",
                                            "leave_skill": "leave_skill", "END": END}
                                  )
    workflow.add_edge("enter_book_hotel", "book_hotel")

    workflow.add_edge("book_hotel_sensitive_tools", "book_hotel")
    workflow.add_edge("book_hotel_safe_tools", "book_hotel")
    workflow.add_conditional_edges(source="book_hotel", path=route_book_hotel,
                                  path_map={"leave_skill": "leave_skill",
                                            "book_hotel_safe_tools": "book_hotel_safe_tools",
                                            "book_hotel_sensitive_tools": "book_hotel_sensitive_tools", "END": END})

    # Excursion Routers
    workflow.add_edge("enter_book_excursion", "book_excursion")

    workflow.add_edge("book_excursion_sensitive_tools", "book_excursion")
    workflow.add_edge("book_excursion_safe_tools", "book_excursion")

    workflow.add_conditional_edges(source="book_excursion", path=route_book_excursion,
                                  path_map={"book_excursion_safe_tools": "book_excursion_safe_tools",
                                            "book_excursion_sensitive_tools": "book_excursion_sensitive_tools",
                                            "leave_skill": "leave_skill", "END": END})
    return workflow

# By Using workflow using langgraph studio
# graph = creat_workflow_graph().compile()