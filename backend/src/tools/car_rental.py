from datetime import date, datetime
from typing import Optional, Union
from langchain_core.runnables import ensure_config
from langchain_core.tools import tool
import pandas as pd


@tool
def search_car_rentals(
    location: Optional[str] = None,
    name: Optional[str] = None,
    price_tier: Optional[str] = None,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
) -> list[dict]:
    """
    Search for car rentals based on location, name, price tier, start date, and end date.

    Args:
        location (Optional[str]): The location of the car rental. Defaults to None.
        name (Optional[str]): The name of the car rental company. Defaults to None.
        price_tier (Optional[str]): The price tier of the car rental. Defaults to None.
        start_date (Optional[Union[datetime, date]]): The start date of the car rental. Defaults to None.
        end_date (Optional[Union[datetime, date]]): The end date of the car rental. Defaults to None.

    Returns:
        list[dict]: A list of car rental dictionaries matching the search criteria.
    """
    config = ensure_config()
    db_session = config["configurable"].get("db_session", None)

    query = "SELECT * FROM car_rentals WHERE "

    if location:
        query += f" location LIKE %'{location}'%"
    if name:
        query += f" AND name LIKE %'{name}'%"
    if price_tier:
        query += f" AND price_tier LIKE %'{price_tier}'%"
    if start_date:
        query += f" AND start_date >= '{start_date}'"
    if end_date:
        query += f" AND end_date <= '{end_date}'"
    # For our tutorial, we will let you match on any dates and price tier.
    # (since our toy dataset doesn't have much data)
    # cursor.execute(query, params)
    # results = cursor.fetchall()

    # conn.close()
    results = pd.read_sql(query, db_session).to_dict(orient="records")
    return results
    # return [
    #     dict(zip([column[0] for column in cursor.description], row)) for row in results
    # ]


@tool
def book_car_rental(rental_id: int) -> str:
    """
    Book a car rental by its ID.

    Args:
        rental_id (int): The ID of the car rental to book.

    Returns:
        str: A message indicating whether the car rental was successfully booked or not.
    """
    # conn = sqlite3.connect(db)
    # cursor = conn.cursor()
    config = ensure_config()
    db_session = config["configurable"].get("db_session", None)
    with db_session.begin() as cursor:
        cursor.execute(f"UPDATE car_rentals SET booked = 1 WHERE id = {rental_id}")

        if cursor.rowcount > 0:
            return f"Car rental {rental_id} successfully booked."
        else:
            return f"No car rental found with ID {rental_id}."


@tool
def update_car_rental(
    rental_id: int,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
) -> str:
    """
    Update a car rental's start and end dates by its ID.

    Args:
        rental_id (int): The ID of the car rental to update.
        start_date (Optional[Union[datetime, date]]): The new start date of the car rental. Defaults to None.
        end_date (Optional[Union[datetime, date]]): The new end date of the car rental. Defaults to None.

    Returns:
        str: A message indicating whether the car rental was successfully updated or not.
    """
    config = ensure_config()
    db_session = config["configurable"].get("db_session", None)
    # conn = sqlite3.connect(db)
    # cursor = conn.cursor()
    with db_session.begin() as cursor:
        if start_date:
            cursor.execute(
                f"UPDATE car_rentals SET start_date = '{start_date}' WHERE id = {rental_id}",
            )
        if end_date:
            cursor.execute(
                f"UPDATE car_rentals SET end_date = '{end_date}' WHERE id = {rental_id}"
            )
        if cursor.rowcount > 0:
            return f"Car rental {rental_id} successfully updated."
        else:
            return f"No car rental found with ID {rental_id}."


@tool
def cancel_car_rental(rental_id: int) -> str:
    """
    Cancel a car rental by its ID.

    Args:
        rental_id (int): The ID of the car rental to cancel.

    Returns:
        str: A message indicating whether the car rental was successfully cancelled or not.
    """
    # conn = sqlite3.connect(db)
    # cursor = conn.cursor()
    config = ensure_config()
    db_session = config["configurable"].get("db_session", None)

    with db_session.begin() as cursor:
        cursor.execute(f"UPDATE car_rentals SET booked = 0 WHERE id = {rental_id}")
        if cursor.rowcount > 0:
            return f"Car rental {rental_id} successfully cancelled."
        else:
            return f"No car rental found with ID {rental_id}."

