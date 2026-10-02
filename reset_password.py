from database import get_connection

email = input("Enter your email: ")
new_password = input("Enter your new password: ")

connection = get_connection()
cursor = connection.cursor()

cursor.execute(
    """
    UPDATE users
    SET password = ?
    WHERE email = ?
    """,
    (new_password, email)
)

connection.commit()

if cursor.rowcount > 0:
    print("Password changed successfully.")
else:
    print("User not found.")

connection.close()
