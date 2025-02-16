from backend.src.tools.hotels import *
from langchain.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import datetime
from backend.src.utilities import CompleteOrEscalate
from pydantic import BaseModel, Field


class ToHotelBookingAssistant(BaseModel):
    """Transfer work to a specialized assistant to handle hotel bookings."""

    location: str = Field(description="The location where the user wants to book a hotel.")
    checkin_date: str = Field(description="The check-in date for the hotel.")
    checkout_date: str = Field(description="The check-out date for the hotel.")
    request: str = Field(
        description="Any additional information or requests from the user regarding the hotel booking."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "location": "Zurich",
                "checkin_date": "2023-08-15",
                "checkout_date": "2023-08-20",
                "request": "I prefer a hotel near the city center with a room that has a view.",
            }
        }


def book_hotel_runnable():
    # Hotel Booking Assistant
    book_hotel_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a specialized assistant for handling hotel bookings. "
                "The primary assistant delegates work to you whenever the user needs help booking a hotel. "
                "Search for available hotels based on the user's preferences and confirm the booking details "
                "with the customer. When searching, be persistent. "
                "Expand your query bounds if the first search returns no results. "
                "If you need more information or the customer changes their mind, "
                "escalate the task back to the main assistant."
                " Remember that a booking isn't completed until after the relevant tool has successfully been used."
                "\nCurrent time: {time}. \n\nIf the user needs help, and none of your tools are appropriate for it, "
                "then 'CompleteOrEscalate' the dialog to the host assistant."
                " Do not waste the user's time. Do not make up invalid tools or functions."
                "\n\nSome examples for which you should CompleteOrEscalate:\n"
                " - 'what's the weather like this time of year?'\n"
                " - 'never mind i think I'll book separately'\n"
                " - 'i need to figure out transportation while i'm there'\n"
                " - 'Oh wait i haven't booked my flight yet i'll do that first'\n"
                " - 'Hotel booking confirmed'",
            ),
            ("placeholder", "{messages}"),
        ]
    ).partial(time=datetime.now)
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite-preview-02-05")
    book_hotel_safe_tools = [search_hotels]
    book_hotel_sensitive_tools = [book_hotel, update_hotel, cancel_hotel]
    book_hotel_tools = book_hotel_safe_tools + book_hotel_sensitive_tools
    return book_hotel_prompt | llm.bind_tools(book_hotel_tools + [CompleteOrEscalate])
