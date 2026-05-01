from flask import Blueprint, session, jsonify, request
from models.db import mysql

fan = Blueprint('fan', __name__)

@fan.route('/follow/<int:artist_id>', methods=['POST'])
def follow_artist(artist_id):
    if 'user_id' not in session:
        return jsonify({"error": "login_required"}), 401

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT IGNORE INTO follows (user_id, artist_id) VALUES (%s,%s)",
        (session['user_id'], artist_id)
    )
    mysql.connection.commit()

    # Get updated followers count
    cur.execute(
        "SELECT COUNT(*) FROM follows WHERE artist_id=%s",
        (artist_id,)
    )
    followers = cur.fetchone()[0]
    cur.close()

    return jsonify({"status": "followed", "followers": followers})


@fan.route('/unfollow/<int:artist_id>', methods=['POST'])
def unfollow_artist(artist_id):
    if 'user_id' not in session:
        return jsonify({"error": "login_required"}), 401

    cur = mysql.connection.cursor()
    cur.execute(
        "DELETE FROM follows WHERE user_id=%s AND artist_id=%s",
        (session['user_id'], artist_id)
    )
    mysql.connection.commit()

    cur.execute(
        "SELECT COUNT(*) FROM follows WHERE artist_id=%s",
        (artist_id,)
    )
    followers = cur.fetchone()[0]
    cur.close()

    return jsonify({"status": "unfollowed", "followers": followers})