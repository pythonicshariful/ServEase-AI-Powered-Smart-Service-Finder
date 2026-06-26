"""
Mistribhai – Backward Compatibility Entry Point
==============================================
You ran `python app.py`. This project has been refactored to use a modular 
blueprint structure. This script forwards to the new entry point.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from servease import create_app

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    with app.app_context():
        from models import db
        db.create_all()
    print("WARNING: You ran app.py. The main entry point is now run.py, but we've forwarded your request.")
    app.run(debug=app.config.get('DEBUG', True))
