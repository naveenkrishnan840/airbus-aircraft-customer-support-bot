from src.tools.excursions import *
from langchain.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import datetime
from src.utilities import CompleteOrEscalate
from pydantic import BaseModel, Field

class ToBookExcursion(BaseModel):
    """Transfers work to a specialized assistant to handle trip recommendation and other excursion bookings."""

    location: str = Field(
        description="The location where the user wants to book a recommended trip."
    )
    request: str = Field(
        description="Any additional information or requests from the user regarding the trip recommendation."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "location": "Lucerne",
                "request": "The user is interested in outdoor activities and scenic views.",
            }
        }


def book_excursion_runnable():
    # Excursion Assistant
    book_excursion_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a specialized assistant for handling trip recommendations. "
                "The primary assistant delegates work to you whenever the user needs help booking a recommended trip. "
                "Search for available trip recommendations based on the user's preferences and confirm the booking "
                "details with the customer. If you need more information or the customer changes their mind, "
                "escalate the task back to the main assistant."
                " When searching, be persistent. Expand your query bounds if the first search returns no results. "
                " Remember that a booking isn't completed until after the relevant tool has successfully been used."
                "\nCurrent time: {time}."
                '\n\nIf the user needs help, and none of your tools are appropriate for it, '
                'then "CompleteOrEscalate" the dialog to the host assistant. Do not waste the user\'s time. '
                'Do not make up invalid tools or functions.'
                "\n\nSome examples for which you should CompleteOrEscalate:\n"
                " - 'nevermind i think I'll book separately'\n"
                " - 'i need to figure out transportation while i'm there'\n"
                " - 'Oh wait i haven't booked my flight yet i'll do that first'\n"
                " - 'Excursion booking confirmed!'",
            ),
            ("placeholder", "{messages}"),
        ]
    ).partial(time=datetime.now)
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
    book_excursion_safe_tools = [search_trip_recommendations]
    book_excursion_sensitive_tools = [book_excursion, update_excursion, cancel_excursion]
    book_excursion_tools = book_excursion_safe_tools + book_excursion_sensitive_tools
    return book_excursion_prompt | llm.bind_tools(book_excursion_tools + [CompleteOrEscalate])
