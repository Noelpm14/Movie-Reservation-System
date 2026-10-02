
import sqlite3
import os


DATABASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "movie_reservation.db"
)


def get_connection():
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
