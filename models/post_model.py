from models.db import mysql
from ml.sentiment import analyze_sentiment

class PostModel:

    @staticmethod
    def create_post(user_id, content):
        sentiment = analyze_sentiment(content)

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO posts (user_id, content, sentiment) VALUES (%s, %s, %s)",
            (user_id, content, sentiment)
        )
        mysql.connection.commit()
        cur.close()

    @staticmethod
    def get_all_posts():
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT 
                posts.id,
                posts.content,
                posts.sentiment,
                posts.created_at,
                users.username
            FROM posts
            JOIN users ON posts.user_id = users.id
            ORDER BY posts.created_at DESC
        """)
        posts = cur.fetchall()
        cur.close()
        return posts

    @staticmethod
    def get_posts_by_user(user_id):
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, content, sentiment, created_at 
            FROM posts WHERE user_id=%s
            ORDER BY created_at DESC
        """, (user_id,))
        posts = cur.fetchall()
        cur.close()
        return posts

    @staticmethod
    def delete_post(post_id, user_id):
        cur = mysql.connection.cursor()
        cur.execute(
            "DELETE FROM posts WHERE id=%s AND user_id=%s",
            (post_id, user_id)
        )
        mysql.connection.commit()
        cur.close()

    @staticmethod
    def get_sentiment_summary():
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT sentiment, COUNT(*) 
            FROM posts GROUP BY sentiment
        """)
        summary = cur.fetchall()
        cur.close()
        return summary
