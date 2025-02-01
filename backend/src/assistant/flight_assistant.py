from backend.src.tools.flights import search_flights, update_ticket_to_new_flight, cancel_ticket
from langchain.prompts import ChatPromptTemplate
from datetime import datetime
from backend.src.utilities import llm, CompleteOrEscalate
from pydantic import BaseModel, Field


class ToFlightBookingAssistant(BaseModel):
    """Transfers work to a specialized assistant to handle flight updates and cancellations."""

    request: str = Field(
        description="Any necessary followup questions the update flight assistant should clarify before proceeding."
    )


def flight_runnable():
    # Flight booking assistant
    flight_booking_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a specialized assistant for handling flight updates. "
                " The primary assistant delegates work to you whenever the user needs help updating their bookings. "
                "Confirm the updated flight details with the customer and inform them of any additional fees. "
                " When searching, be persistent. Expand your query bounds if the first search returns no results. "
                "If you need more information or the customer changes their mind, escalate the task back to the "
                "main assistant."
                " Remember that a booking isn't completed until after the relevant tool has successfully been used."
                "\n\nCurrent user flight information:\n<Flights>\n{user_info}\n</Flights>"
                "\nCurrent time: {time}."
                "\n\nIf the user needs help, and none of your tools are appropriate for it, then"
                ' "CompleteOrEscalate" the dialog to the host assistant. Do not waste the user\'s time. '
                'Do not make up invalid tools or functions.',
            ),
            ("placeholder", "{messages}"),
        ]
    ).partial(time=datetime.now)

    update_flight_safe_tools = [search_flights]
    update_flight_sensitive_tools = [cancel_ticket, update_ticket_to_new_flight]
    update_flight_tools = update_flight_safe_tools + update_flight_sensitive_tools

    update_flight_runnable = (flight_booking_prompt |
                              llm.bind_tools(update_flight_tools + [CompleteOrEscalate]))

    return update_flight_runnable
