from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Provider, ProviderSkill, ServicePost
from forms import RegisterForm, LoginForm, ProviderProfileForm, SkillForm, PostForm
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change_this_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///servease.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ----------------- helpers -----------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def simple_match_score(post, provider):
    """
    MVP matching: count keyword overlaps between post title/desc and provider skills.
    Returns integer score.
    """
    text = (post.title + ' ' + (post.description or '')).lower()
    score = 0
    for s in provider.skills:
        if s.skill.lower() in text:
            score += 2
        else:
            # partial match by token
            for token in s.skill.lower().split():
                if token in text:
                    score += 1
    # small boost by rating and verification
    score += int(provider.rating or 0)
    if provider.verified:
        score += 2
    return score

# ----------------- routes -----------------
@app.route('/')
def home():
    return render_template('home.html')

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        hashed = generate_password_hash(form.password.data)
        user = User(name=form.name.data, email=form.email.data, password=hashed, role=form.role.data)
        db.session.add(user)
        db.session.commit()
        # If provider role, create provider profile row
        if user.role == 'provider':
            prov = Provider(user_id=user.id, title='', description='')
            db.session.add(prov)
            db.session.commit()
        flash('Registered! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html', form=form)

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('home'))

# Dashboard (redirect based on role)
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'provider':
        return redirect(url_for('provider_dashboard'))
    return redirect(url_for('finder_dashboard'))

# Provider dashboard
@app.route('/provider')
@login_required
def provider_dashboard():
    if current_user.role != 'provider':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    prov = current_user.provider
    skills = ProviderSkill.query.filter_by(provider_id=prov.id).all()
    form = ProviderProfileForm()
    # Pre-fill form with current provider data for convenience
    form.title.data = prov.title
    form.description.data = prov.description
    return render_template('provider_dashboard.html', provider=prov, skills=skills, form=form)

# Add / edit provider profile
@app.route('/provider/profile', methods=['GET', 'POST'])
@login_required
def provider_profile():
    if current_user.role != 'provider':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    form = ProviderProfileForm()
    prov = current_user.provider
    if form.validate_on_submit():
        prov.title = form.title.data
        prov.description = form.description.data
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('provider_dashboard'))
    form.title.data = prov.title
    form.description.data = prov.description
    return render_template('provider_dashboard.html', provider=prov, skills=prov.skills, form=form)

# Add skill
@app.route('/provider/add-skill', methods=['GET', 'POST'])
@login_required
def add_skill():
    if current_user.role != 'provider':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    form = SkillForm()
    if form.validate_on_submit():
        prov = current_user.provider
        sk = ProviderSkill(provider_id=prov.id, skill=form.skill.data.strip())
        db.session.add(sk)
        db.session.commit()
        flash('Skill added.', 'success')
        return redirect(url_for('provider_dashboard'))
    return render_template('add_skill.html', form=form)

# Finder dashboard
@app.route('/finder')
@login_required
def finder_dashboard():
    if current_user.role != 'finder':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    posts = ServicePost.query.filter_by(finder_id=current_user.id).order_by(ServicePost.created_at.desc()).all()
    return render_template('finder_dashboard.html', posts=posts)

# Create post
@app.route('/post/create', methods=['GET', 'POST'])
@login_required
def create_post():
    if current_user.role != 'finder':
        flash('Only finders can create posts.', 'danger')
        return redirect(url_for('dashboard'))
    form = PostForm()
    if form.validate_on_submit():
        post = ServicePost(
            finder_id=current_user.id,
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            location=form.location.data.strip(),
            budget_min=form.budget_min.data or 0,
            budget_max=form.budget_max.data or 0
        )
        db.session.add(post)
        db.session.commit()
        flash('Post created! Matching providers...', 'success')
        return redirect(url_for('view_matches', post_id=post.id))
    return render_template('create_post.html', form=form)

# View matches (simple)
@app.route('/post/<int:post_id>/matches')
@login_required
def view_matches(post_id):
    post = ServicePost.query.get_or_404(post_id)
    # find providers in DB and compute simple score
    providers = Provider.query.all()
    scored = []
    for p in providers:
        # skip provider if no user
        if not p.user:
            continue
        score = simple_match_score(post, p)
        scored.append((score, p))
    # sort desc
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [item[1] for item in scored[:10]]  # top 10
    return render_template('view_matches.html', post=post, matches=top, scored=scored[:10])

# Run
if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists('servease.db'):
            db.create_all()
            print("Database created: servease.db")
    app.run(debug=True)
