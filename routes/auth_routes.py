from flask import Blueprint, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from models.db import mysql

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users(username,email,password,role) VALUES(%s,%s,%s,'fan')",
                    (username,email,password))
        mysql.connection.commit()
        return redirect('/login')
    return render_template('register.html')


@auth.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['role'] = user[4]
            return redirect('/feed')

    return render_template('login.html')
