from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models.db import mysql
import MySQLdb.cursors

auth = Blueprint('auth', __name__)

# ----------------- REGISTER -----------------
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('user_routes.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not email or not password or not confirm_password:
            flash("All fields are required.", "danger")
            return redirect(url_for('auth.register'))

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('auth.register'))

        hashed_password = generate_password_hash(password)

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            cur.close()
            flash("Email already registered!", "warning")
            return redirect(url_for('auth.register'))

        cur.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, 'fan')",
            (username, email, hashed_password)
        )
        mysql.connection.commit()
        cur.close()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for('auth.login'))

    return render_template('register.html')


# ----------------- LOGIN -----------------
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('user_routes.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash("Email and password required.", "danger")
            return redirect(url_for('auth.login'))

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()

        if not user:
            flash("Email not found.", "danger")
            return redirect(url_for('auth.login'))

        if not check_password_hash(user['password'], password):
            flash("Incorrect password.", "danger")
            return redirect(url_for('auth.login'))

        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']

        flash(f"Welcome, {user['username']} 💜", "success")
        return redirect(url_for('user_routes.dashboard'))

    return render_template('login.html')


# ----------------- LOGOUT -----------------
@auth.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('auth.login'))
