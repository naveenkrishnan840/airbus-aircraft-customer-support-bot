from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig, ensure_config
import pytz
from sqlalchemy import text
from datetime import date, datetime
from typing import Optional
import pandas as pd


@tool
def fetch_user_flight_information(config: RunnableConfig) -> list[dict]:
    """Fetch all tickets for the user along with corresponding flight information and seat assignments.

    Returns:
        A list of dictionaries where each dictionary contains the ticket details,
        associated flight details, and the seat assignments for each ticket belonging to the user.
    """
    configuration = config.get("configurable", {})
    passenger_id = configuration.get("passenger_id", None)
    db_session = configuration.get("db_session", None)
    if not passenger_id:
        raise ValueError("No passenger ID configured.")

    # conn = sqlite3.connect(db)
    # cursor = conn.cursor()

    query = """
    SELECT 
        t.ticket_no, t.book_ref,
        f.flight_id, f.flight_no, f.departure_airport, f.arrival_airport, f.scheduled_departure, f.scheduled_arrival,
        bp.seat_no, tf.fare_conditions
    FROM 
        tickets t
        JOIN ticket_flights tf ON t.ticket_no = tf.ticket_no
        JOIN flights f ON tf.flight_id = f.flight_id
        JOIN boarding_passes bp ON bp.ticket_no = t.ticket_no AND bp.flight_id = f.flight_id
    WHERE
        t.passenger_id = '{0}'
    """.format(passenger_id)
    # query = query.format(passenger_id)
    results = pd.read_sql(query, db_session).to_dict(orient="records")
    # cursor.execute(query, (passenger_id,))
    # rows = cursor.fetchall()
    # column_names = [column[0] for column in cursor.description]
    # results = [dict(zip(column_names, row)) for row in rows]

    # cursor.close()
    # conn.close()

    return results


@tool
def search_flights(
    departure_airport: Optional[str] = None,
    arrival_airport: Optional[str] = None,
    start_time: Optional[date | datetime] = None,
    end_time: Optional[date | datetime] = None,
    limit: int = 20,
) -> list[dict]:
    """Search for flights based on departure airport, arrival airport, and departure time range."""
    config = ensure_config()
    db_session = config["configurable"].get("db_session", None)

    query = "SELECT * FROM flights WHERE "

    if departure_airport:
        query += f" departure_airport = '{departure_airport}'"

    if arrival_airport:
        query += f" AND arrival_airport = '{arrival_airport}'"

    if start_time:
        query += f" AND scheduled_departure >= '{start_time}'"

    if end_time:
        query += f" AND scheduled_departure <= '{end_time}'"
    query += f" LIMIT {limit}"
    results = pd.read_sql(query, db_session).to_dict(orient="records")
    # cursor.execute(query, params)
    # rows = cursor.fetchall()
    # column_names = [column[0] for column in cursor.description]
    # results = [dict(zip(column_names, row)) for row in rows]

    # cursor.close()
    # conn.close()

    return results


@tool
def update_ticket_to_new_flight(
    ticket_no: str, new_flight_id: int, *, config: RunnableConfig
) -> str:
    """Update the user's ticket to a new valid flight."""
    configuration = config.get("configurable", {})
    passenger_id = configuration.get("passenger_id", None)
    db_session = configuration.get("db_session", None)
    if not passenger_id:
        raise ValueError("No passenger ID configured.")

    # conn = sqlite3.connect(db)
    # cursor = conn.cursor()

    # cursor.execute(
    #     "SELECT departure_airport, arrival_airport, scheduled_departure FROM flights WHERE flight_id = ?",
    #     (new_flight_id,),
    # )
    new_flight = pd.read_sql(sql=f"SELECT departure_airport, arrival_airport, scheduled_departure FROM flights WHERE "
                                 f"flight_id = {new_flight_id}", con=db_session)
    # new_flight = cursor.fetchone()
    if new_flight.empty:
        # cursor.close()
        # conn.close()
        return "Invalid new flight ID provided."
    # column_names = [column[0] for column in cursor.description]
    # new_flight_dict = dict(zip(column_names, new_flight))
    timezone = pytz.timezone("Etc/GMT-3")
    current_time = datetime.now(tz=timezone)
    departure_time = datetime.strptime(
        new_flight.loc["scheduled_departure"], "%Y-%m-%d %H:%M:%S.%f%z"
    )
    time_until = (departure_time - current_time).total_seconds()
    if time_until < (3 * 3600):
        return (f"Not permitted to reschedule to a flight that is less than 3 hours from the current time. "
                f"Selected flight is at {departure_time}.")

    # cursor.execute(
    #     "SELECT flight_id FROM ticket_flights WHERE ticket_no = ?", (ticket_no,)
    # )
    current_flight = pd.read_sql(sql=f"SELECT flight_id FROM ticket_flights WHERE ticket_no = '{ticket_no}'",
                                 con=db_session)
    # current_flight = cursor.fetchone()
    if current_flight.empty:
        # cursor.close()
        # conn.close()
        return "No existing ticket found for the given ticket number."

    # Check the signed-in user actually has this ticket
    # cursor.execute(
    #     "SELECT * FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
    #     (ticket_no, passenger_id),
    # )
    current_ticket = pd.read_sql(f"SELECT * FROM tickets WHERE ticket_no = '{ticket_no}' "
                                 f"AND passenger_id = '{passenger_id}'", db_session)
    # current_ticket = cursor.fetchone()
    if current_ticket.empty:
        # cursor.close()
        # conn.close()
        return f"Current signed-in passenger with ID {passenger_id} not the owner of ticket {ticket_no}"

    # In a real application, you'd likely add additional checks here to enforce business logic,
    # like "does the new departure airport match the current ticket", etc.
    # While it's best to try to be *proactive* in 'type-hinting' policies to the LLM
    # it's inevitably going to get things wrong, so you **also** need to ensure your
    # API enforces valid behavior
    # cursor.execute(
    #     "UPDATE ticket_flights SET flight_id = ? WHERE ticket_no = ?",
    #     (new_flight_id, ticket_no),
    # )
    with db_session.begin() as conn:
        conn.execute(text(f"UPDATE ticket_flights SET flight_id = {new_flight_id} WHERE ticket_no = {ticket_no}"))

    # pd.read_sql(sql="UPDATE ticket_flights SET flight_id = '{0}' WHERE ticket_no = '{1}'".
    #             format(new_flight_id, ticket_no), con=db_session)
    # conn.commit()

    # cursor.close()
    # conn.close()
    return "Ticket successfully updated to new flight."


@tool
def cancel_ticket(ticket_no: str, *, config: RunnableConfig) -> str:
    """Cancel the user's ticket and remove it from the database."""
    configuration = config.get("configurable", {})
    passenger_id = configuration.get("passenger_id", None)
    db_session = configuration.get("db_session", None)
    if not passenger_id:
        raise ValueError("No passenger ID configured.")
    # conn = sqlite3.connect(db)
    # cursor = conn.cursor()

    # cursor.execute(
    #     "SELECT flight_id FROM ticket_flights WHERE ticket_no = ?", (ticket_no,)
    # )
    existing_ticket = pd.read_sql(f"SELECT flight_id FROM ticket_flights WHERE ticket_no = '{ticket_no}'",
                                  db_session)
    # existing_ticket = cursor.fetchone()
    if existing_ticket.empty:
        # cursor.close()
        # conn.close()
        return "No existing ticket found for the given ticket number."

    # Check the signed-in user actually has this ticket
    # cursor.execute(
    #     "SELECT flight_id FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
    #     (ticket_no, passenger_id),
    # )
    current_ticket = pd.read_sql(sql=f"SELECT flight_id FROM tickets WHERE ticket_no = '{ticket_no}' "
                                     f"AND passenger_id = '{passenger_id}'", con=db_session)
    # current_ticket = cursor.fetchone()
    if current_ticket.empty:
        # cursor.close()
        # conn.close()
        return f"Current signed-in passenger with ID {passenger_id} not the owner of ticket {ticket_no}"
    with db_session.begin() as cursor:
        cursor.execute(text(f"DELETE FROM ticket_flights WHERE ticket_no = {ticket_no}"))
    # pd.read_sql(f"DELETE FROM ticket_flights WHERE ticket_no = '{ticket_no}'", db_session)
    # conn.commit()

    # cursor.close()
    # conn.close()
    return "Ticket successfully cancelled."

