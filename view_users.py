from database import get_connection

connection = get_connection()
cursor = connection.cursor()

cursor.execute("SELECT * FROM users")
users = cursor.fetchall()

for user in users:
    print("ID:", user["id"])
    print("Name:", user["name"])
    print("Email:", user["email"])
    print("Role:", user["role"])
    print("--------------------")

connection.close()
