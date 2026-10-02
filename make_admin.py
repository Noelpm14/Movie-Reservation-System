from database import get_connection


email = input("Enter the email of the user to make admin: ")


connection = get_connection()
cursor = connection.cursor()


cursor.execute(
    """
    UPDATE users
    SET role = 'admin'
    WHERE email = ?
    """,
    (email,)
)


connection.commit()


if cursor.rowcount > 0:
    print("User is now an admin.")
else:
    print("User not found.")


connection.close()
