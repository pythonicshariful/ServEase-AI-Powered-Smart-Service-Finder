"""
Mistribhai – Application Entry Point
====================================
Run with:  python run.py
Or with:   flask --app run run
Or Gunicorn: gunicorn "run:app"
"""
import os
from dotenv import load_dotenv

load_dotenv()

from servease import create_app
import click

app = create_app(os.environ.get('FLASK_ENV', 'development'))

@app.cli.command("make-admin")
@click.argument("email")
def make_admin(email):
    import click
    from models import db, User
    user = User.query.filter_by(email=email).first()
    if not user:
        click.echo(f"User with email {email} not found.")
        return
    user.role = 'admin'
    db.session.commit()
    click.echo(f"Success! {email} is now an admin.")

if __name__ == '__main__':
    with app.app_context():
        from models import db
        db.create_all()
    app.run(debug=app.config.get('DEBUG', True))
