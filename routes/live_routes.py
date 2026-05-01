from flask import Blueprint, render_template

live = Blueprint('live', __name__)

@live.route('/live')
def live_feed():
    # List of 4 live streams
    videos = [
        {
            'title': 'BTS Live Concert',
            'url': 'https://www.youtube.com/embed/S4x1dY1pHPI',
            'description': 'Watch BTS live now!'
        },
        {
            'title': 'Stray Kids Fan Meet',
            'url': 'https://www.youtube.com/embed/kpTNfq4sEw8',
            'description': 'Join Stray Kids live.'
        },
        {
            'title': 'BLACKPINK Live Event',
            'url': 'https://www.youtube.com/embed/BLACKPINK_CHANNEL_ID',
            'description': 'BLACKPINK performing live.'
        },
        {
            'title': 'TXT Online Showcase',
            'url': 'https://www.youtube.com/embed/TXT_CHANNEL_ID',
            'description': 'TXT live performance.'
        }
    ]
    return render_template('live.html', videos=videos)
