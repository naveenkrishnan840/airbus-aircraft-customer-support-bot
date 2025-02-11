import requests
import sqlite3
import pandas as pd
from sqlalchemy import create_engine, text

db_url = "https://storage.googleapis.com/benchmarks-artifacts/travel-db/travel2.sqlite"
local_file = "travel2.sqlite"
# The backup lets us restart for each tutorial section
backup_file = "travel2.backup.sqlite"

response = requests.get(db_url)
response.raise_for_status()  # Ensure the request was successful
with open(local_file, "wb") as f:
    f.write(response.content)

conn = sqlite3.connect(local_file)
tables = pd.read_sql("SELECT name FROM sqlite_master where type='table';", conn)
tables = tables.name.to_list()

tdf = {}
for t in tables:
    tdf[t] = pd.read_sql(f"SELECT * from {t}", conn)


example_time = pd.to_datetime(
        tdf["flights"]["actual_departure"].replace("\\N", pd.NaT)
    ).max()
current_time = pd.to_datetime("now").tz_localize(example_time.tz)
time_diff = current_time - example_time

tdf["bookings"]["book_date"] = (
    pd.to_datetime(tdf["bookings"]["book_date"].replace("\\N", pd.NaT), utc=True)
    + time_diff
)

datetime_columns = [
    "scheduled_departure",
    "scheduled_arrival",
    "actual_departure",
    "actual_arrival",
]

for column in datetime_columns:
    tdf["flights"][column] = (
        pd.to_datetime(tdf["flights"][column].replace("\\N", pd.NaT)) + time_diff
    )

tdf["aircrafts_data"] = tdf["aircrafts_data"][tdf["aircrafts_data"]["model"] == "Airbus A319-100"]
tdf["aircrafts_data"].reset_index(drop=True, inplace=True)

tdf["airports_data"] = tdf["airports_data"][tdf["airports_data"]["airport_code"].isin(
    ['BKK', 'DEN', 'SHA', 'SFO', 'AKL','BOS', 'CAN', 'DME', 'SEZ', 'DUS', 'SYD', 'LIS', 'PNH', 'DAC', 'OSL', 'AMS',
     'LHR', 'HAM', 'BSL', 'ARN', 'ATH', 'DUB', 'GVA', 'MSP', 'PRG'])]

tdf["airports_data"].reset_index(drop=True, inplace=True)

tdf["flights"] = tdf["flights"][tdf["flights"]["aircraft_code"] == "319"]
tdf["flights"].reset_index(drop=True, inplace=True)

tdf["boarding_passes"] = tdf["boarding_passes"][tdf["boarding_passes"]["flight_id"].isin(tdf["flights"]["flight_id"])]
tdf["boarding_passes"].reset_index(drop=True, inplace=True)

tdf["ticket_flights"] = tdf["ticket_flights"][tdf["ticket_flights"]["flight_id"].isin(tdf["flights"]["flight_id"])]
tdf["ticket_flights"].reset_index(drop=True, inplace=True)

tdf["tickets"] = tdf["tickets"][tdf["tickets"]["ticket_no"].isin(tdf["ticket_flights"]["ticket_no"])]
tdf["tickets"].reset_index(drop=True, inplace=True)

tdf["bookings"] = tdf["bookings"][tdf["bookings"]["book_ref"].isin(tdf["tickets"]["book_ref"])]
tdf["bookings"].reset_index(drop=True, inplace=True)


tdf["seats"] = tdf["seats"][tdf["seats"]["aircraft_code"] == "319"]
tdf["seats"].reset_index(drop=True, inplace=True)


SQLALCHEMY_DATABASE_URL = (f"mysql+pymysql://debian_sys_maint:PL17UchUtriTr0bas#ic8TRoxl8@dhee-platform."
                           f"ccxstins9jm3.ap-southeast-1.rds.amazonaws.com/travel_support")

print(SQLALCHEMY_DATABASE_URL)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20, max_overflow=0, echo_pool="debug",
)

with engine.begin() as cursor:
    for table in tables:
        cursor.execute(text(f"truncate table {table}"))

for table_name, df in tdf.items():
    df.to_sql(table_name, engine, if_exists="replace", index=False)

