from flask import Blueprint, render_template, request, session, redirect
from models.db import mysql
from ml.sentiment import analyze_sentiment

post = Blueprint('post', __name__)

@post.route('/feed', methods=['GET','POST'])
def feed():
    if request.method == 'POST':
        content = request.form['content']
        sentiment = analyze_sentiment(content)

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO posts(user_id,content,sentiment) VALUES(%s,%s,%s)",
                    (session['user_id'],content,sentiment))
        mysql.connection.commit()

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT posts.content, posts.sentiment, users.username 
        FROM posts JOIN users ON posts.user_id = users.id
        ORDER BY posts.created_at DESC
    """)
    posts = cur.fetchall()

    return render_template('feed.html', posts=posts)
