#library
from typing import Callable
import warnings

import pandas as pd
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import tools_condition
from langgraph.graph import START, END
from fastapi import FastAPI, APIRouter, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pathlib import Path
import json
import uuid
import os
from dotenv import load_dotenv
from langchain.tools.tavily_search import TavilySearchResults
from langsmith import Client
from langchain_core.tracers.context import tracing_v2_enabled
# Local file
from backend.src.tools.flights import *
from backend.src.assistant.flight_assistant import flight_runnable, ToFlightBookingAssistant
from backend.src.tools.lookup_policies_retriever_tool import lookup_policy
from backend.src.utilities import *
# assistance file library
from backend.src.assistant.car_rental_assistant import car_rental_runnable, ToBookCarRental
from backend.src.assistant.hotel_assistant import book_hotel_runnable, ToHotelBookingAssistant
from backend.src.assistant.excursion_assistant import book_excursion_runnable, ToBookExcursion
from backend.src.assistant.primary_assistant import primary_assistant_runnable
# tools file library
from backend.src.tools.car_rental import search_car_rentals, book_car_rental, update_car_rental, cancel_car_rental
from backend.src.tools.hotels import cancel_hotel, book_hotel, update_hotel, search_hotels
from backend.src.tools.excursions import (book_excursion, update_excursion, cancel_excursion,
                                          search_trip_recommendations)
from backend.src.database_conn import get_session_local
from backend.src.request_validate import BotRequest

load_dotenv()
warnings.filterwarnings("ignore")
client = Client(api_key=os.getenv("LANGCHAIN_API_KEY"))


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


builder = StateGraph(State)


def user_info(state: State):
    return {"user_info": fetch_user_flight_information.invoke({})}


builder.add_node("fetch_user_info", user_info)

# Primary assistant
builder.add_node("primary_assistant", Assistant(primary_assistant_runnable()))

primary_assistant_tools = [TavilySearchResults(max_results=1), search_flights, lookup_policy]
builder.add_node(
    "primary_assistant_tools", create_tool_node_with_fallback(primary_assistant_tools)
)

# Flight booking assistant
builder.add_node(
    "enter_update_flight",
    create_entry_node("Flight Updates & Booking Assistant", "update_flight"),
)

builder.add_node("update_flight", Assistant(flight_runnable()))
update_flight_sensitive_tools = [cancel_ticket, update_ticket_to_new_flight]
builder.add_node(
    "update_flight_sensitive_tools",
    create_tool_node_with_fallback(update_flight_sensitive_tools),
)
update_flight_safe_tools = [search_flights]
builder.add_node(
    "update_flight_safe_tools",
    create_tool_node_with_fallback(update_flight_safe_tools),
)

# Car rental assistant

builder.add_node(
    "enter_book_car_rental",
    create_entry_node(assistant_name="Car Rental Assistant", new_dialog_state="book_car_rental"),
)
builder.add_node("book_car_rental", Assistant(car_rental_runnable()))

book_car_rental_safe_tools = [search_car_rentals]
builder.add_node(
    "book_car_rental_safe_tools",
    create_tool_node_with_fallback(book_car_rental_safe_tools),
)
book_car_rental_sensitive_tools = [
    book_car_rental,
    update_car_rental,
    cancel_car_rental,
]

builder.add_node(
    "book_car_rental_sensitive_tools",
    create_tool_node_with_fallback(book_car_rental_sensitive_tools),
)

# Hotel booking assistant
builder.add_node(
    "enter_book_hotel", create_entry_node(assistant_name="Hotel Booking Assistant", new_dialog_state="book_hotel")
)

builder.add_node("book_hotel", Assistant(book_hotel_runnable()))

book_hotel_safe_tools = [search_hotels]
builder.add_node(
    "book_hotel_safe_tools",
    create_tool_node_with_fallback(book_hotel_safe_tools),
)

book_hotel_sensitive_tools = [book_hotel, update_hotel, cancel_hotel]
builder.add_node(
    "book_hotel_sensitive_tools",
    create_tool_node_with_fallback(book_hotel_sensitive_tools),
)

# Excursion assistant
builder.add_node(
    "enter_book_excursion",
    create_entry_node(assistant_name="Trip Recommendation Assistant", new_dialog_state="book_excursion"),
)

builder.add_node("book_excursion", Assistant(book_excursion_runnable()))

book_excursion_safe_tools = [search_trip_recommendations]
builder.add_node(
    "book_excursion_safe_tools",
    create_tool_node_with_fallback(book_excursion_safe_tools),
)

book_excursion_sensitive_tools = [book_excursion, update_excursion, cancel_excursion]
builder.add_node(
    "book_excursion_sensitive_tools",
    create_tool_node_with_fallback(book_excursion_sensitive_tools),
)

# Start Adding Edges
builder.add_edge(START, "fetch_user_info")


# Each delegated workflow can directly respond to the user
# When the user responds, we want to return to the currently active workflow
def route_to_workflow(
        state: State,
) -> Literal[
    "primary_assistant",
    "update_flight",
    "book_car_rental",
    "book_hotel",
    "book_excursion",
]:
    """If we are in a delegated state, route directly to the appropriate assistant."""
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"
    return dialog_state[-1]


builder.add_conditional_edges(source="fetch_user_info", path=route_to_workflow,
                              path_map={"primary_assistant": "primary_assistant", "update_flight": "update_flight",
                                        "book_car_rental": "book_car_rental", "book_hotel": "book_hotel",
                                        "book_excursion": "book_excursion"})


# Primary Assistant Routers
def route_primary_assistant(
        state: State,
):
    route = tools_condition(state)
    if route == END:
        return "END"
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        if tool_calls[0]["name"] == ToFlightBookingAssistant.__name__:
            return "enter_update_flight"
        elif tool_calls[0]["name"] == ToBookCarRental.__name__:
            return "enter_book_car_rental"
        elif tool_calls[0]["name"] == ToHotelBookingAssistant.__name__:
            return "enter_book_hotel"
        elif tool_calls[0]["name"] == ToBookExcursion.__name__:
            return "enter_book_excursion"
        return "primary_assistant_tools"
    raise ValueError("Invalid route")


# The assistant can route to one of the delegated assistants,
# directly use a tool, or directly respond to the user
builder.add_conditional_edges(source="primary_assistant", path=route_primary_assistant,
                              path_map={"enter_update_flight": "enter_update_flight",
                                        "enter_book_car_rental": "enter_book_car_rental",
                                        "enter_book_hotel": "enter_book_hotel",
                                        "enter_book_excursion": "enter_book_excursion",
                                        "primary_assistant_tools": "primary_assistant_tools",
                                        "END": END}
                              )
builder.add_edge("primary_assistant_tools", "primary_assistant")
builder.add_edge("enter_update_flight", "update_flight")


def route_update_flight(
        state: State,
):
    route = tools_condition(state)
    if route == END:
        return "END"
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    if did_cancel:
        return "leave_skill"
    safe_toolnames = [t.name for t in update_flight_safe_tools]
    if all(tc["name"] in safe_toolnames for tc in tool_calls):
        return "update_flight_safe_tools"
    return "update_flight_sensitive_tools"


builder.add_edge("update_flight_sensitive_tools", "update_flight")
builder.add_edge("update_flight_safe_tools", "update_flight")
builder.add_conditional_edges(source="update_flight", path=route_update_flight,
                              path_map={"update_flight_sensitive_tools": "update_flight_sensitive_tools",
                                        "update_flight_safe_tools": "update_flight_safe_tools",
                                        "leave_skill": "leave_skill", "END": END}
                              )
builder.add_edge("leave_skill", "primary_assistant")
builder.add_edge("enter_book_car_rental", "book_car_rental")


def route_book_car_rental(
        state: State,
):
    route = tools_condition(state)
    if route == END:
        return "END"
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    if did_cancel:
        return "leave_skill"
    safe_toolnames = [t.name for t in book_car_rental_safe_tools]
    if all(tc["name"] in safe_toolnames for tc in tool_calls):
        return "book_car_rental_safe_tools"
    return "book_car_rental_sensitive_tools"


builder.add_edge("book_car_rental_sensitive_tools", "book_car_rental")
builder.add_edge("book_car_rental_safe_tools", "book_car_rental")
builder.add_conditional_edges(source="book_car_rental", path=route_book_car_rental,
                              path_map={"book_car_rental_safe_tools": "book_car_rental_safe_tools",
                                        "book_car_rental_sensitive_tools": "book_car_rental_sensitive_tools",
                                        "leave_skill": "leave_skill", "END": END}
                              )
builder.add_edge("enter_book_hotel", "book_hotel")


def route_book_hotel(
        state: State,
):
    route = tools_condition(state)
    if route == END:
        return "END"
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    if did_cancel:
        return "leave_skill"
    tool_names = [t.name for t in book_hotel_safe_tools]
    if all(tc["name"] in tool_names for tc in tool_calls):
        return "book_hotel_safe_tools"
    return "book_hotel_sensitive_tools"


builder.add_edge("book_hotel_sensitive_tools", "book_hotel")
builder.add_edge("book_hotel_safe_tools", "book_hotel")
builder.add_conditional_edges(source="book_hotel", path=route_book_hotel,
                              path_map={"leave_skill": "leave_skill", "book_hotel_safe_tools": "book_hotel_safe_tools",
                                        "book_hotel_sensitive_tools": "book_hotel_sensitive_tools", "END": END})

# Excursion Routers
builder.add_edge("enter_book_excursion", "book_excursion")


def route_book_excursion(
        state: State,
):
    route = tools_condition(state)
    if route == END:
        return "END"
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    if did_cancel:
        return "leave_skill"
    tool_names = [t.name for t in book_excursion_safe_tools]
    if all(tc["name"] in tool_names for tc in tool_calls):
        return "book_excursion_safe_tools"
    return "book_excursion_sensitive_tools"


builder.add_edge("book_excursion_sensitive_tools", "book_excursion")
builder.add_edge("book_excursion_safe_tools", "book_excursion")

builder.add_conditional_edges(source="book_excursion", path=route_book_excursion,
                              path_map={"book_excursion_safe_tools": "book_excursion_safe_tools",
                                        "book_excursion_sensitive_tools": "book_excursion_sensitive_tools",
                                        "leave_skill": "leave_skill", "END": END})


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


builder.add_node("leave_skill", pop_dialog_state)

app = FastAPI(title="Customer Support Chat Bot Application")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env_path = Path("./") / ".env"
if os.path.exists(env_path):
    load_dotenv(env_path)

api_router = APIRouter()


@api_router.post("/get-passenger-id")
async def get_passenger(request: Request, db_session=Depends(get_session_local)):
    try:
        query = """
        SELECT 
            t.passenger_id
        FROM 
            tickets t
            JOIN ticket_flights tf ON t.ticket_no = tf.ticket_no
            JOIN flights f ON tf.flight_id = f.flight_id
            JOIN boarding_passes bp ON bp.ticket_no = t.ticket_no AND bp.flight_id = f.flight_id
        ORDER BY RAND() LIMIT 10
        """
        result = pd.read_sql(query, db_session)["passenger_id"].to_list()
        return HTTPException(status_code=200, detail=result)
    except Exception as e:
        raise e


@api_router.post("/compile-langgraph")
async def compile_langgraph(request: Request, session=Depends(get_session_local)):
    memory = MemorySaver()
    compiled_graph = builder.compile(
        checkpointer=memory,
        # Let the user approve or deny the use of sensitive tools
        interrupt_before=[
            "update_flight_sensitive_tools",
            "book_car_rental_sensitive_tools",
            "book_hotel_sensitive_tools",
            "book_excursion_sensitive_tools",
        ],
    )
    thread_id = uuid.uuid4()
    config = {
        "configurable": {
            # The passenger_id is used in our flight tools to
            # fetch the user's flight information
            # "passenger_id": "3442 587242",
            # Checkpoints are accessed by thread_id
            "thread_id": thread_id.hex,
            "db_session": session
        }
    }
    request.app.state.compiled_graph = compiled_graph
    # request.session["graph_config"] = config
    request.app.state.graph_config = config
    return HTTPException(status_code=200, detail="success")


async def stream_agent_response(request, compiled_graph, config, input_msg, interrupt_status, interrupt_user_input):
    try:
        _printed = set()
        # We can reuse the tutorial questions from part 1 to see how it does.
        with (tracing_v2_enabled(project_name=os.getenv("LANGCHAIN_PROJECT"), client=client)):
            snapshot = compiled_graph.get_state(config)
            # if interrupt_status is None and snapshot.next:
            #     bot_response_content = json.dumps({"bot_response": "", "interrupt": "yes"})
            #     yield bot_response_content
            # else:
            if snapshot.next and interrupt_status == "yes":
                result = compiled_graph.invoke(None, config)
                bot_response_content = json.dumps({"bot_response": result["messages"][-1].content,
                                                   "interrupt": "no"})
                request.app.state.compiled_graph = compiled_graph
                yield bot_response_content
            elif snapshot.next and interrupt_status == "no":
                result = compiled_graph.invoke({
                    "messages": [
                        ToolMessage(
                            tool_call_id=snapshot.values['messages'][-1].tool_call_id,
                            content=f"API call denied by user. Reasoning: '{interrupt_user_input}'. "
                                    f"Continue assisting, accounting for the user's input.",
                            name=snapshot.values["messages"][-1].toll_calls[0]["name"])]},
                    config)
                bot_response_content = json.dumps({"bot_response": result["messages"][-1].content,
                                                   "interrupt": "no"})
                request.app.state.compiled_graph = compiled_graph
                yield bot_response_content
            else:
                events = compiled_graph.stream(input=
                                               {"messages": ("user", input_msg.strip() if input_msg else None)},
                                               config=config, stream_mode="updates")
                for st in events:
                    try:
                        snapshot = compiled_graph.get_state(config)
                        if interrupt_status is None and snapshot.next and "__interrupt__" in st:
                            bot_response_content = json.dumps({"bot_response": "", "interrupt": "yes"})
                            request.app.state.compiled_graph = compiled_graph
                            yield bot_response_content
                            break
                        elif list(st.keys())[0] in ["primary_assistant", "update_flight", "book_car_rental",
                                                    "book_excursion", "book_hotel"]:
                            bot_response = st[list(st.keys())[0]]["messages"]
                            if bot_response.content:
                                bot_response_content = json.dumps({"bot_response": bot_response.content,
                                                                   "interrupt": "no"})
                                request.app.state.compiled_graph = compiled_graph
                                yield bot_response_content
                    except Exception as e:
                        raise e

            # for question in tutorial_questions:
            #     events = compiled_graph.stream(
            #         {"messages": ("user", question)}, config, stream_mode="values"
            #     )
            #     generation_response = [st for st in events]
            #     for event in events:
            #         print_event(event, _printed)
            #     snapshot = compiled_graph.get_state(config)
            #     while snapshot.next:
            #         # We have an interrupt! The agent is trying to use a tool, and the user can approve or deny it
            #         # Note: This code is all outside of your graph. Typically, you would stream the output to a UI.
            #         # Then, you would have the frontend trigger a new run via an API call when the user has provided input.
            #         try:
            #             user_input = input(
            #                 "Do you approve of the above actions? Type 'y' to continue;"
            #                 " otherwise, explain your requested changed.\n\n"
            #             )
            #         except:
            #             user_input = "y"
            #         if user_input.strip() == "y":
            #             # Just continue
            #             result = compiled_graph.invoke(
            #                 None,
            #                 config,
            #             )
            #         else:
            #             # Satisfy the tool invocation by
            #             # providing instructions on the requested changes / change of mind
            #             result = compiled_graph.invoke(
            #                 {
            #                     "messages": [
            #                         ToolMessage(
            #                             tool_call_id=event["messages"][-1].tool_calls[0]["id"],
            #                             content=f"API call denied by user. Reasoning: '{user_input}'. Continue assisting, accounting for the user's input.",
            #                         )
            #                     ]
            #                 },
            #                 config,
            #             )
            #         snapshot = compiled_graph.get_state(config)
    except Exception as e:
        raise e


@api_router.post("/bot-message-request")
async def generate_bot_message(request: Request, bot_request: BotRequest):
    print(bot_request)
    config = request.app.state.graph_config
    compiled_graph = request.app.state.compiled_graph
    config["configurable"]["passenger_id"] = bot_request.passengerId
    interrupt_user_input = bot_request.interrupt_user_input
    return StreamingResponse(stream_agent_response(request, compiled_graph, config, bot_request.input_msg,
                                                   bot_request.interrupt_status, interrupt_user_input),
                             media_type="text/event-stream")


app.include_router(api_router)
# local changes
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8006)
