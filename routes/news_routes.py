from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from models.db import mysql
import MySQLdb.cursors

news_bp = Blueprint('news', __name__)

# ---------- SENTIMENT ----------
def analyze_sentiment(text):
    text = text.lower()
    positive_words = ['love','amazing','great','awesome','happy','excited','legend','best']
    negative_words = ['hate','bad','worst','boring','disappointed','angry','sad']

    pos = sum(word in text for word in positive_words)
    neg = sum(word in text for word in negative_words)

    if pos > neg:
        return 'Positive'
    elif neg > pos:
        return 'Negative'
    return 'Neutral'


# ---------- NEWS LIST ----------
@news_bp.route('/news')
def news_feed():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get page number from query string, default = 1
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    # Fetch 10 news for this page
    cur.execute("SELECT * FROM news ORDER BY created_at DESC LIMIT %s OFFSET %s", (per_page, offset))
    news_items = cur.fetchall()

    # Total news count
    cur.execute("SELECT COUNT(*) as total FROM news")
    total = cur.fetchone()['total']

    cur.close()

    # Calculate if next page exists
    next_page = page + 1 if offset + per_page < total else None
    prev_page = page - 1 if page > 1 else None

    return render_template('news.html',
                           news_items=news_items,
                           next_page=next_page,
                           prev_page=prev_page)

#----------------news detail--------------
@news_bp.route('/news/<int:news_id>', methods=['GET', 'POST'])
def news_detail(news_id):
    if 'user_id' not in session:
        flash("Login to view and comment", "warning")
        return redirect(url_for('auth.login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Current news
    cur.execute("SELECT * FROM news WHERE id=%s", (news_id,))
    news = cur.fetchone()
    if not news:
        abort(404)

    # Add comment
    if request.method == 'POST':
        comment = request.form.get('comment')
        sentiment = analyze_sentiment(comment)

        cur.execute(
            "INSERT INTO news_comments (news_id, user_id, comment, sentiment) VALUES (%s,%s,%s,%s)",
            (news_id, session['user_id'], comment, sentiment)
        )
        mysql.connection.commit()
        flash("Comment added!", "success")
        return redirect(url_for('news.news_detail', news_id=news_id))

    # Fetch comments
    cur.execute("""
        SELECT c.comment, c.sentiment, c.created_at, u.username
        FROM news_comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.news_id=%s
        ORDER BY c.id DESC
    """, (news_id,))
    comments = cur.fetchall()

    # Fetch previous news
    cur.execute("SELECT id, title FROM news WHERE id < %s ORDER BY id DESC LIMIT 1", (news_id,))
    prev_news = cur.fetchone()

    # Fetch next news
    cur.execute("SELECT id, title FROM news WHERE id > %s ORDER BY id ASC LIMIT 1", (news_id,))
    next_news = cur.fetchone()

    cur.close()
    return render_template('news_detail.html',
                           news=news,
                           comments=comments,
                           prev_news=prev_news,
                           next_news=next_news)

   