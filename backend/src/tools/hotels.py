from datetime import date, datetime
from typing import Optional, Union
import pandas as pd
from sqlalchemy import text
from langchain_core.tools import tool
from langchain_core.runnables import ensure_config


@tool
def search_hotels(
    location: Optional[str] = None,
    name: Optional[str] = None,
    price_tier: Optional[str] = None,
    checkin_date: Optional[Union[datetime, date]] = None,
    checkout_date: Optional[Union[datetime, date]] = None,
) -> list[dict]:
    """
    Search for hotels based on location, name, price tier, check-in date, and check-out date.

    Args:
        location (Optional[str]): The location of the hotel. Defaults to None.
        name (Optional[str]): The name of the hotel. Defaults to None.
        price_tier (Optional[str]): The price tier of the hotel. Defaults to None. Examples: Midscale, Upper Midscale, Upscale, Luxury
        checkin_date (Optional[Union[datetime, date]]): The check-in date of the hotel. Defaults to None.
        checkout_date (Optional[Union[datetime, date]]): The check-out date of the hotel. Defaults to None.

    Returns:
        list[dict]: A list of hotel dictionaries matching the search criteria.
    """
    # conn = sqlite3.connect(db)
    # cursor = conn.cursor()
    config = ensure_config()
    db_session = config["configurable"].get("db_session", None)
    query = "SELECT * FROM hotels WHERE "
    params = []

    if location:
        query += f" location LIKE %'{location}'%"
    if name:
        query += f" AND name LIKE %'{name}'%"
    # For the sake of this tutorial, we will let you match on any dates and price tier.
    results = pd.read_sql(query, db_session).to_dict(orient="records")
    return results
    # cursor.execute(query, params)
    # results = cursor.fetchall()

    # conn.close()

    # return [
    #     dict(zip([column[0] for column in cursor.description], row)) for row in results
    # ]


@tool
def book_hotel(hotel_id: int) -> str:
    """
    Book a hotel by its ID.

    Args:
        hotel_id (int): The ID of the hotel to book.

    Returns:
        str: A message indicating whether the hotel was successfully booked or not.
    """
    config = ensure_config()
    db_session = config["configurable"].get("db_session", None)
    # conn = sqlite3.connect(db)
    # cursor = conn.cursor()
    with db_session.begin() as cursor:
        cursor.execute(text(f"UPDATE hotels SET booked = 1 WHERE id = {hotel_id}"))
        if cursor.rowcount > 0:
            return f"Hotel {hotel_id} successfully booked."
        else:
            return f"No hotel found with ID {hotel_id}."


@tool
def update_hotel(
    hotel_id: int,
    checkin_date: Optional[Union[datetime, date]] = None,
    checkout_date: Optional[Union[datetime, date]] = None,
) -> str:
    """
    Update a hotel's check-in and check-out dates by its ID.

    Args:
        hotel_id (int): The ID of the hotel to update.
        checkin_date (Optional[Union[datetime, date]]): The new check-in date of the hotel. Defaults to None.
        checkout_date (Optional[Union[datetime, date]]): The new check-out date of the hotel. Defaults to None.

    Returns:
        str: A message indicating whether the hotel was successfully updated or not.
    """
    # conn = sqlite3.connect(db)
    # cursor = conn.cursor()
    config = ensure_config()
    db_session = config["configurable"].get("db_session", None)

    with db_session.begin() as cursor:
        if checkin_date:
            cursor.execute(
                text(f"UPDATE hotels SET checkin_date = {checkin_date} WHERE id = {hotel_id}")
            )
        if checkout_date:
            cursor.execute(
                text(f"UPDATE hotels SET checkout_date = {checkout_date} WHERE id = {hotel_id}")
            )

    if cursor.rowcount > 0:
        return f"Hotel {hotel_id} successfully updated."
    else:
        return f"No hotel found with ID {hotel_id}."


@tool
def cancel_hotel(hotel_id: int) -> str:
    """
    Cancel a hotel by its ID.

    Args:
        hotel_id (int): The ID of the hotel to cancel.

    Returns:
        str: A message indicating whether the hotel was successfully cancelled or not.
    """
    # conn = sqlite3.connect(db)
    # cursor = conn.cursor()
    config = ensure_config()
    db_session = config["configurable"].get("db_session", None)

    with db_session.begin() as cursor:
        cursor.execute(text(f"UPDATE hotels SET booked = 0 WHERE id = {hotel_id}"))
        if cursor.rowcount > 0:
            return f"Hotel {hotel_id} successfully cancelled."
        else:
            return f"No hotel found with ID {hotel_id}."

