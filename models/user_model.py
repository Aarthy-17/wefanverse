from models.db import mysql
from werkzeug.security import generate_password_hash, check_password_hash

class UserModel:

    @staticmethod
    def create_user(username, email, password, role='fan'):
        hashed_password = generate_password_hash(password)

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
            (username, email, hashed_password, role)
        )
        mysql.connection.commit()
        cur.close()

    @staticmethod
    def get_user_by_email(email):
        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, username, email, password, role FROM users WHERE email=%s",
            (email,)
        )
        user = cur.fetchone()
        cur.close()
        return user

    @staticmethod
    def get_user_by_id(user_id):
        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, username, email, role FROM users WHERE id=%s",
            (user_id,)
        )
        user = cur.fetchone()
        cur.close()
        return user

    @staticmethod
    def validate_login(email, password):
        user = UserModel.get_user_by_email(email)
        if user and check_password_hash(user[3], password):
            return user
        return None

    @staticmethod
    def get_all_users():
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, email, role FROM users")
        users = cur.fetchall()
        cur.close()
        return users
    
    @staticmethod
    def reset_password(email, new_password):
         hashed_password = generate_password_hash(new_password)
         cur = mysql.connection.cursor()
         cur.execute( "UPDATE users SET password=%s WHERE email=%s",(hashed_password, email))
         mysql.connection.commit()
         cur.close()

