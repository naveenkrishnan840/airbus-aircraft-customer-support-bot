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

from src.build_graph import creat_workflow_graph
from src.database_conn import get_session_local
from src.request_validate import BotRequest

load_dotenv()
warnings.filterwarnings("ignore")
client = Client(api_key=os.getenv("LANGCHAIN_API_KEY"))



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

graph_builder = creat_workflow_graph()

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
    compiled_graph = graph_builder.compile(
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
            snapshot = compiled_graph.get_state(config=config)
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
    try:
        print(bot_request)
        config = request.app.state.graph_config
        compiled_graph = request.app.state.compiled_graph
        config["configurable"]["passenger_id"] = bot_request.passengerId
        interrupt_user_input = bot_request.interrupt_user_input
        return StreamingResponse(stream_agent_response(request, compiled_graph, config, bot_request.input_msg,
                                                       bot_request.interrupt_status, interrupt_user_input),
                                 media_type="text/event-stream")
    except Exception as e:
        raise e


app.include_router(api_router)
# local changes
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8006)
