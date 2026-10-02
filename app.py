
from database import get_connection
from datetime import datetime
import hashlib
import hmac
import secrets


ITERATIONS = 300000


def hash_password(password):
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        ITERATIONS
    ).hex()

    return f"pbkdf2_sha256${ITERATIONS}${salt}${password_hash}"


def verify_password(password, stored_password):
    if not stored_password.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password, stored_password)

    try:
        _, iterations, salt, expected_hash = stored_password.split("$")

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations)
        ).hex()

        return hmac.compare_digest(actual_hash, expected_hash)

    except (ValueError, TypeError):
        return False


def read_positive_integer(prompt):
    value = input(prompt).strip()

    try:
        number = int(value)
        if number <= 0:
            raise ValueError
        return number
    except ValueError:
        print("Enter a positive whole number.")
        return None


def read_price(prompt):
    value = input(prompt).strip()

    try:
        price = float(value)
        if not price > 0 or not price < float("inf"):
            raise ValueError
        return round(price, 2)
    except ValueError:
        print("Enter a valid price greater than zero.")
        return None


def signup():
    print("\n===== SIGN UP =====")

    name = input("Name: ").strip()
    email = input("Email: ").strip().lower()
    password = input("Password: ")

    if not name or not email or not password:
        print("All fields are required.")
        return

    if len(password) < 8:
        print("Use a password with at least 8 characters.")
        return

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, 'user')
            """,
            (name, email, hash_password(password))
        )

        connection.commit()
        print("Account created successfully!")

    except sqlite3.IntegrityError:
        print("That email is already registered.")

    finally:
        connection.close()


def login():
    print("\n===== LOGIN =====")

    email = input("Email: ").strip().lower()
    password = input("Password: ")

    connection = get_connection()

    try:
        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if user is None or not verify_password(
            password, user["password"]
        ):
            print("Invalid email or password.")
            return

        if not user["password"].startswith("pbkdf2_sha256$"):
            connection.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (hash_password(password), user["id"])
            )
            connection.commit()

        user = connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user["id"],)
        ).fetchone()

    finally:
        connection.close()

    print("\nLogin successful!")
    print("Welcome,", user["name"])

    if user["role"] == "admin":
        admin_menu()
    else:
        user_menu(user)


def add_movie():
    print("\n===== ADD MOVIE =====")

    title = input("Movie title: ").strip()
    description = input("Description: ").strip()
    genre = input("Genre: ").strip()

    if not title or not genre:
        print("Title and genre are required.")
        return

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO movies (title, description, genre)
            VALUES (?, ?, ?)
            """,
            (title, description, genre)
        )

        connection.commit()
        print("Movie added successfully!")

    finally:
        connection.close()


def view_movies():
    print("\n===== MOVIES =====")

    connection = get_connection()

    try:
        movies = connection.execute(
            "SELECT * FROM movies ORDER BY id"
        ).fetchall()

        if not movies:
            print("No movies found.")
            return

        for movie in movies:
            print("\nID:", movie["id"])
            print("Title:", movie["title"])
            print("Description:", movie["description"])
            print("Genre:", movie["genre"])
            print("--------------------")

    finally:
        connection.close()


def delete_movie():
    view_movies()

    movie_id = read_positive_integer("\nMovie ID to delete: ")
    if movie_id is None:
        return

    connection = get_connection()

    try:
        movie = connection.execute(
            "SELECT id FROM movies WHERE id = ?",
            (movie_id,)
        ).fetchone()

        if movie is None:
            print("Movie not found.")
            return

        count = connection.execute(
            "SELECT COUNT(*) FROM showtimes WHERE movie_id = ?",
            (movie_id,)
        ).fetchone()[0]

        if count:
            print("Cannot delete a movie that has showtimes.")
            print("Remove its showtimes first.")
            return

        connection.execute(
            "DELETE FROM movies WHERE id = ?",
            (movie_id,)
        )

        connection.commit()
        print("Movie deleted.")

    finally:
        connection.close()


def add_showtime():
    print("\n===== ADD SHOWTIME =====")

    view_movies()

    movie_id = read_positive_integer("Movie ID: ")
    if movie_id is None:
        return

    show_date = input("Date (YYYY-MM-DD): ").strip()
    show_time = input("Time (HH:MM, 24-hour): ").strip()
    ticket_price = read_price("Ticket price: ")
    total_seats = read_positive_integer("Total seat capacity: ")

    if ticket_price is None or total_seats is None:
        return

    try:
        datetime.strptime(show_date, "%Y-%m-%d")
        datetime.strptime(show_time, "%H:%M")
    except ValueError:
        print("Enter a valid date and time.")
        return

    show_datetime = datetime.strptime(
        show_date + " " + show_time,
        "%Y-%m-%d %H:%M"
    )

    if show_datetime <= datetime.now():
        print("Choose a future date and time.")
        return

    connection = get_connection()

    try:
        movie = connection.execute(
            "SELECT id FROM movies WHERE id = ?",
            (movie_id,)
        ).fetchone()

        if movie is None:
            print("Movie not found.")
            return

        connection.execute(
            """
            INSERT INTO showtimes
            (movie_id, show_date, show_time, ticket_price, total_seats)
            VALUES (?, ?, ?, ?, ?)
            """,
            (movie_id, show_date, show_time,
             ticket_price, total_seats)
        )

        connection.commit()
        print("Showtime added successfully!")

    finally:
        connection.close()


def view_showtimes():
    print("\n===== SHOWTIMES =====")

    connection = get_connection()

    try:
        shows = connection.execute(
            """
            SELECT
                s.id,
                m.title,
                s.show_date,
                s.show_time,
                s.ticket_price,
                s.total_seats,
                COALESCE(
                    SUM(
                        CASE WHEN r.status = 'booked'
                        THEN r.seats_booked ELSE 0 END
                    ), 0
                ) AS booked_seats
            FROM showtimes s
            JOIN movies m ON m.id = s.movie_id
            LEFT JOIN reservations r ON r.showtime_id = s.id
            GROUP BY s.id
            ORDER BY s.show_date, s.show_time
            """
        ).fetchall()

        if not shows:
            print("No showtimes scheduled.")
            return

        for show in shows:
            print("\nShowtime ID:", show["id"])
            print("Movie:", show["title"])
            print("Date:", show["show_date"])
            print("Time:", show["show_time"])
            print("Ticket price:", show["ticket_price"])
            print("Total seats:", show["total_seats"])
            print("Available seats:",
                  show["total_seats"] - show["booked_seats"])
            print("--------------------")

    finally:
        connection.close()


def delete_showtime():
    view_showtimes()

    showtime_id = read_positive_integer(
        "\nShowtime ID to delete: "
    )

    if showtime_id is None:
        return

    connection = get_connection()

    try:
        show = connection.execute(
            """
            SELECT show_date, show_time
            FROM showtimes WHERE id = ?
            """,
            (showtime_id,)
        ).fetchone()

        if show is None:
            print("Showtime not found.")
            return

        show_datetime = datetime.strptime(
            show["show_date"] + " " + show["show_time"],
            "%Y-%m-%d %H:%M"
        )

        if show_datetime <= datetime.now():
            print("Only upcoming showtimes can be deleted.")
            return

        count = connection.execute(
            "SELECT COUNT(*) FROM reservations WHERE showtime_id = ?",
            (showtime_id,)
        ).fetchone()[0]

        if count:
            print("This showtime has reservation history.")
            print("Keep it to preserve booking records.")
            return

        connection.execute(
            "DELETE FROM showtimes WHERE id = ?",
            (showtime_id,)
        )

        connection.commit()
        print("Showtime deleted.")

    finally:
        connection.close()


def reserve_seats(user):
    view_showtimes()

    showtime_id = read_positive_integer(
        "\nShowtime ID to book: "
    )
    seats = read_positive_integer("Number of seats: ")

    if showtime_id is None or seats is None:
        return

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        show = connection.execute(
            """
            SELECT id, show_date, show_time, total_seats
            FROM showtimes WHERE id = ?
            """,
            (showtime_id,)
        ).fetchone()

        if show is None:
            print("Showtime not found.")
            return

        show_datetime = datetime.strptime(
            show["show_date"] + " " + show["show_time"],
            "%Y-%m-%d %H:%M"
        )

        if show_datetime <= datetime.now():
            print("This show has already started or passed.")
            return

        booked = connection.execute(
            """
            SELECT COALESCE(SUM(seats_booked), 0)
            FROM reservations
            WHERE showtime_id = ? AND status = 'booked'
            """,
            (showtime_id,)
        ).fetchone()[0]

        available = show["total_seats"] - booked

        if seats > available:
            print("Not enough seats available.")
            print("Seats remaining:", available)
            return

        booking_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor = connection.execute(
            """
            INSERT INTO reservations
            (user_id, showtime_id, seats_booked, booking_date, status)
            VALUES (?, ?, ?, ?, 'booked')
            """,
            (user["id"], showtime_id, seats, booking_date)
        )

        connection.commit()

        print("Reservation successful!")
        print("Reservation ID:", cursor.lastrowid)
        print("Seats booked:", seats)
        print("Seats remaining:", available - seats)

    except sqlite3.Error as error:
        connection.rollback()
        print("Booking failed:", error)

    finally:
        connection.close()


def my_reservations(user):
    print("\n===== MY RESERVATIONS =====")

    connection = get_connection()

    try:
        reservations = connection.execute(
            """
            SELECT
                r.id,
                m.title,
                s.show_date,
                s.show_time,
                r.seats_booked,
                r.booking_date,
                r.status
            FROM reservations r
            JOIN showtimes s ON s.id = r.showtime_id
            JOIN movies m ON m.id = s.movie_id
            WHERE r.user_id = ?
            ORDER BY r.id DESC
            """,
            (user["id"],)
        ).fetchall()

        if not reservations:
            print("You have no reservations.")
            return

        for reservation in reservations:
            print("\nReservation ID:", reservation["id"])
            print("Movie:", reservation["title"])
            print("Date:", reservation["show_date"])
            print("Time:", reservation["show_time"])
            print("Seats:", reservation["seats_booked"])
            print("Booked on:", reservation["booking_date"])
            print("Status:", reservation["status"])

    finally:
        connection.close()


def cancel_reservation(user):
    my_reservations(user)

    reservation_id = read_positive_integer(
        "\nReservation ID to cancel: "
    )

    if reservation_id is None:
        return

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        reservation = connection.execute(
            """
            SELECT r.id, s.show_date, s.show_time
            FROM reservations r
            JOIN showtimes s ON s.id = r.showtime_id
            WHERE r.id = ?
              AND r.user_id = ?
              AND r.status = 'booked'
            """,
            (reservation_id, user["id"])
        ).fetchone()

        if reservation is None:
            print("Active reservation not found.")
            return

        show_datetime = datetime.strptime(
            reservation["show_date"] + " " + reservation["show_time"],
            "%Y-%m-%d %H:%M"
        )

        if show_datetime <= datetime.now():
            print("Only upcoming reservations can be cancelled.")
            return

        connection.execute(
            """
            UPDATE reservations
            SET status = 'cancelled'
            WHERE id = ? AND user_id = ?
            """,
            (reservation_id, user["id"])
        )

        connection.commit()
        print("Reservation cancelled successfully.")

    except sqlite3.Error as error:
        connection.rollback()
        print("Cancellation failed:", error)

    finally:
        connection.close()


def admin_reservations():
    print("\n===== ALL RESERVATIONS =====")

    connection = get_connection()

    try:
        reservations = connection.execute(
            """
            SELECT
                r.id,
                u.name,
                u.email,
                m.title,
                s.show_date,
                s.show_time,
                r.seats_booked,
                r.booking_date,
                r.status,
                s.ticket_price
            FROM reservations r
            JOIN users u ON u.id = r.user_id
            JOIN showtimes s ON s.id = r.showtime_id
            JOIN movies m ON m.id = s.movie_id
            ORDER BY r.id DESC
            """
        ).fetchall()

        if not reservations:
            print("No reservations found.")
            return

        for reservation in reservations:
            print("\nReservation ID:", reservation["id"])
            print("Customer:", reservation["name"])
            print("Email:", reservation["email"])
            print("Movie:", reservation["title"])
            print("Date:", reservation["show_date"])
            print("Time:", reservation["show_time"])
            print("Seats:", reservation["seats_booked"])
            print("Status:", reservation["status"])

    finally:
        connection.close()


def revenue_report():
    print("\n===== REVENUE REPORT =====")

    connection = get_connection()

    try:
        total = connection.execute(
            """
            SELECT COALESCE(
                SUM(r.seats_booked * s.ticket_price), 0
            )
            FROM reservations r
            JOIN showtimes s ON s.id = r.showtime_id
            WHERE r.status = 'booked'
            """
        ).fetchone()[0]

        print("Revenue from active reservations:", round(total, 2))

        rows = connection.execute(
            """
            SELECT
                m.title,
                SUM(r.seats_booked) AS seats,
                SUM(r.seats_booked * s.ticket_price) AS revenue
            FROM reservations r
            JOIN showtimes s ON s.id = r.showtime_id
            JOIN movies m ON m.id = s.movie_id
            WHERE r.status = 'booked'
            GROUP BY m.id, m.title
            ORDER BY m.title
            """
        ).fetchall()

        for row in rows:
            print("\nMovie:", row["title"])
            print("Seats booked:", row["seats"])
            print("Revenue:", round(row["revenue"], 2))

    finally:
        connection.close()


def manage_users():
    print("\n===== USER ACCOUNTS =====")

    connection = get_connection()

    try:
        users = connection.execute(
            "SELECT id, name, email, role FROM users ORDER BY id"
        ).fetchall()

        for user in users:
            print(
                user["id"],
                user["name"],
                user["email"],
                user["role"]
            )

        user_id = read_positive_integer(
            "\nUser ID to promote to admin (0 to return): "
        )

        if user_id is None:
            return

        if user_id == 0:
            return

        target = connection.execute(
            "SELECT id, role FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if target is None:
            print("User not found.")
            return

        connection.execute(
            "UPDATE users SET role = 'admin' WHERE id = ?",
            (user_id,)
        )

        connection.commit()
        print("User promoted to admin.")

    finally:
        connection.close()


def admin_menu():
    while True:
        print("\n===== ADMIN MENU =====")
        print("1. Add Movie")
        print("2. View Movies")
        print("3. Delete Movie")
        print("4. Add Showtime")
        print("5. View Showtimes")
        print("6. Delete Showtime")
        print("7. All Reservations")
        print("8. Revenue Report")
        print("9. Manage Users")
        print("10. Logout")

        choice = input("Choice: ").strip()

        if choice == "1":
            add_movie()
        elif choice == "2":
            view_movies()
        elif choice == "3":
            delete_movie()
        elif choice == "4":
            add_showtime()
        elif choice == "5":
            view_showtimes()
        elif choice == "6":
            delete_showtime()
        elif choice == "7":
            admin_reservations()
        elif choice == "8":
            revenue_report()
        elif choice == "9":
            manage_users()
        elif choice == "10":
            print("Logged out.")
            break
        else:
            print("Invalid choice.")


def user_menu(user):
    while True:
        print("\n===== USER MENU =====")
        print("1. Browse Movies")
        print("2. View Showtimes")
        print("3. Reserve Seats")
        print("4. My Reservations")
        print("5. Cancel Reservation")
        print("6. Logout")

        choice = input("Choice: ").strip()

        if choice == "1":
            view_movies()
        elif choice == "2":
            view_showtimes()
        elif choice == "3":
            reserve_seats(user)
        elif choice == "4":
            my_reservations(user)
        elif choice == "5":
            cancel_reservation(user)
        elif choice == "6":
            print("Logged out.")
            break
        else:
            print("Invalid choice.")


def main():
    while True:
        print("\n===== MOVIE RESERVATION SYSTEM =====")
        print("1. Sign Up")
        print("2. Login")
        print("3. Exit")

        choice = input("Choice: ").strip()

        if choice == "1":
            signup()
        elif choice == "2":
            login()
        elif choice == "3":
            print("Thank you for using the system!")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    import sqlite3
    main()
