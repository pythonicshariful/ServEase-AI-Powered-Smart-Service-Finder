from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
import os
import time
from datetime import datetime
from models import db, User, Provider, ProviderSkill, ServicePost, Finder
from forms import RegisterForm, LoginForm, ProviderProfileForm, SkillForm, PostForm, FinderProfileForm
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change_this_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///servease.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File upload configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Create upload folders if they don't exist
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'covers'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'portfolio'), exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file, folder):
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{current_user.id}_{int(time.time())}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
        file.save(filepath)
        return f'uploads/{folder}/{filename}'
    return None


# Jinja filter: human-friendly time delta (e.g. "3 days ago")
@app.template_filter('timeago')
def timeago(dt):
    """Return a human-friendly time difference between now and `dt`.
    Handles naive datetimes stored in DB.
    """
    if not dt:
        return ''
    if isinstance(dt, str):
        # try parsing ISO format
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    now = datetime.utcnow()
    # ensure dt is naive UTC-like for comparison
    if dt.tzinfo is not None:
        try:
            dt = dt.replace(tzinfo=None)
        except Exception:
            pass
    diff = now - dt if now >= dt else dt - now
    seconds = diff.total_seconds()
    intervals = (
        ('year', 31536000),
        ('month', 2592000),
        ('week', 604800),
        ('day', 86400),
        ('hour', 3600),
        ('minute', 60),
        ('second', 1),
    )
    for name, count in intervals:
        value = int(seconds // count)
        if value:
            return f"{value} {name}{'s' if value > 1 else ''} ago"
    return 'just now'


# Register a fromjson filter for templates (converts JSON string to Python object)
@app.template_filter('fromjson')
def fromjson(s):
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}

# Gemini API configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')  # Set this as environment variable
if GEMINI_API_KEY:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro')
else:
    gemini_model = None

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

def gemini_match_providers(post, providers):
    """
    Use Gemini AI to intelligently match service posts with providers.
    Returns list of tuples (score, provider) sorted by relevance.
    """
    if not gemini_model:
        # Fallback to simple matching if Gemini is not configured
        scored = []
        for p in providers:
            if p.user:
                score = simple_match_score(post, p)
                scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored
    
    try:
        # Prepare provider data for Gemini
        provider_data = []
        for p in providers:
            if not p.user:
                continue
            skills = ', '.join([s.skill for s in p.skills])
            provider_info = {
                'id': p.id,
                'name': p.user.name,
                'title': p.title or 'No title',
                'description': p.description or 'No description',
                'skills': skills or 'No skills',
                'location': p.location or 'Not specified',
                'verified': p.verified,
                'rating': p.rating or 0
            }
            provider_data.append(provider_info)
        
        if not provider_data:
            return []
        
        # Create prompt for Gemini
        prompt = f"""You are a service matching AI. Analyze the following service post and rank the providers by relevance.

Service Post:
Title: {post.title}
Description: {post.description or 'No description'}
Location: {post.location or 'Not specified'}
Budget: {post.budget_min or 0} - {post.budget_max or 0} BDT

Providers:
{chr(10).join([f"ID {p['id']}: {p['name']} - {p['title']}, Skills: {p['skills']}, Location: {p['location']}, Verified: {p['verified']}, Rating: {p['rating']}" for p in provider_data])}

Rank the providers by relevance (1-100 scale) and return ONLY a comma-separated list of provider IDs in order of best match first.
Format: ID1,ID2,ID3,etc"""

        response = gemini_model.generate_content(prompt)
        ranked_ids = [int(x.strip()) for x in response.text.split(',') if x.strip().isdigit()]
        
        # Create scored list with high scores for AI-ranked providers
        scored = []
        base_score = len(provider_data)
        for idx, prov_id in enumerate(ranked_ids):
            provider = next((p for p in providers if p.id == prov_id), None)
            if provider:
                # Give higher scores to earlier ranked providers
                score = base_score - idx + 10  # Add 10 base score
                if provider.verified:
                    score += 5
                scored.append((score, provider))
        
        # Add unranked providers with lower scores
        for p in providers:
            if p.user and p.id not in ranked_ids:
                score = simple_match_score(post, p)
                scored.append((score, p))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored
        
    except Exception as e:
        print(f"Gemini matching error: {e}")
        # Fallback to simple matching
        scored = []
        for p in providers:
            if p.user:
                score = simple_match_score(post, p)
                scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

def gemini_match_posts(provider, posts):
    """
    Use Gemini AI to intelligently match providers with service posts.
    Returns list of tuples (score, post) sorted by relevance.
    """
    if not gemini_model:
        # Fallback to simple matching if Gemini is not configured
        scored = []
        for post in posts:
            score = simple_match_score(post, provider)
            scored.append((score, post))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored
    
    try:
        # Prepare post data for Gemini
        post_data = []
        for post in posts:
            if post.status != 'open':
                continue
            post_info = {
                'id': post.id,
                'title': post.title,
                'description': post.description or 'No description',
                'location': post.location or 'Not specified',
                'budget': f"{post.budget_min or 0} - {post.budget_max or 0} BDT"
            }
            post_data.append(post_info)
        
        if not post_data:
            return []
        
        # Create prompt for Gemini
        skills = ', '.join([s.skill for s in provider.skills])
        prompt = f"""You are a service matching AI. Analyze the following service provider and rank the job posts by relevance.

Service Provider:
Name: {provider.user.name}
Title: {provider.title or 'No title'}
Description: {provider.description or 'No description'}
Skills: {skills or 'No skills'}
Location: {provider.location or 'Not specified'}
Verified: {provider.verified}
Rating: {provider.rating or 0}

Job Posts:
{chr(10).join([f"ID {p['id']}: {p['title']}, Description: {p['description']}, Location: {p['location']}, Budget: {p['budget']}" for p in post_data])}

Rank the job posts by relevance (1-100 scale) and return ONLY a comma-separated list of post IDs in order of best match first.
Format: ID1,ID2,ID3,etc"""

        response = gemini_model.generate_content(prompt)
        ranked_ids = [int(x.strip()) for x in response.text.split(',') if x.strip().isdigit()]
        
        # Create scored list with high scores for AI-ranked posts
        scored = []
        base_score = len(post_data)
        for idx, post_id in enumerate(ranked_ids):
            post = next((p for p in posts if p.id == post_id), None)
            if post:
                # Give higher scores to earlier ranked posts
                score = base_score - idx + 10  # Add 10 base score
                scored.append((score, post))
        
        # Add unranked posts with lower scores
        for post in posts:
            if post.status == 'open' and post.id not in ranked_ids:
                score = simple_match_score(post, provider)
                scored.append((score, post))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored
        
    except Exception as e:
        print(f"Gemini matching error: {e}")
        # Fallback to simple matching
        scored = []
        for post in posts:
            if post.status == 'open':
                score = simple_match_score(post, provider)
                scored.append((score, post))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

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
        # Create profile based on role
        if user.role == 'provider':
            prov = Provider(user_id=user.id, title='', description='', location='')
            db.session.add(prov)
        elif user.role == 'finder':
            finder = Finder(user_id=user.id, bio='', location='')
            db.session.add(finder)
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

# User Profile
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    if current_user.role == 'provider':
        form = ProviderProfileForm()
    else:
        form = FinderProfileForm()

    if form.validate_on_submit():
        # Handle profile image upload
        if form.profile_image.data:
            profile_path = save_image(form.profile_image.data, 'profiles')
            if profile_path:
                # Delete old profile image if it exists
                if current_user.profile_image:
                    old_path = os.path.join(app.root_path, 'static', current_user.profile_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                current_user.profile_image = profile_path

        # Handle cover image upload
        if form.cover_image.data:
            cover_path = save_image(form.cover_image.data, 'covers')
            if cover_path:
                # Delete old cover image if it exists
                if current_user.cover_image:
                    old_path = os.path.join(app.root_path, 'static', current_user.cover_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                current_user.cover_image = cover_path

        # Update common user fields
        current_user.name = form.name.data
        current_user.tagline = form.tagline.data
        current_user.phone = form.phone.data
        current_user.website = form.website.data
        current_user.location = form.location.data
        
        # Update social links
        social_links = {
            'facebook': form.facebook.data,
            'twitter': form.twitter.data,
            'linkedin': form.linkedin.data
        }
        current_user.social_links = json.dumps(social_links)

        if current_user.role == 'provider':
            provider = current_user.provider
            provider.title = form.title.data
            provider.description = form.description.data
            provider.business_name = form.business_name.data
            provider.experience_years = form.experience_years.data
            provider.hourly_rate = form.hourly_rate.data
            provider.location = form.location.data

            # Handle portfolio images
            if form.portfolio_images.data:
                portfolio_images = []
                existing_images = json.loads(provider.portfolio_images) if provider.portfolio_images else []
                
                # Delete old portfolio images
                for old_image in existing_images:
                    old_path = os.path.join(app.root_path, 'static', old_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Save new portfolio images
                for image in form.portfolio_images.data:
                    if image:
                        portfolio_path = save_image(image, 'portfolio')
                        if portfolio_path:
                            portfolio_images.append(portfolio_path)
                
                provider.portfolio_images = json.dumps(portfolio_images)

        else:
            finder = current_user.finder
            finder.bio = form.bio.data
            finder.company_name = form.company_name.data
            finder.company_size = form.company_size.data
            finder.industry = form.industry.data
            finder.location = form.location.data
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('user_profile'))

    # Pre-fill form
    form.name.data = current_user.name
    form.tagline.data = current_user.tagline
    form.phone.data = current_user.phone
    form.website.data = current_user.website
    form.location.data = current_user.location

    # Pre-fill social links
    if current_user.social_links:
        social_links = json.loads(current_user.social_links)
        form.facebook.data = social_links.get('facebook', '')
        form.twitter.data = social_links.get('twitter', '')
        form.linkedin.data = social_links.get('linkedin', '')

    posts = None
    if current_user.role == 'provider':
        provider = current_user.provider
        form.title.data = provider.title
        form.description.data = provider.description
        form.business_name.data = provider.business_name
        form.experience_years.data = provider.experience_years
        form.hourly_rate.data = provider.hourly_rate
        skills = provider.skills
        try:
            portfolio_images = json.loads(provider.portfolio_images) if provider and provider.portfolio_images else []
        except Exception:
            portfolio_images = []
    else:
        finder = current_user.finder
        form.bio.data = finder.bio
        form.company_name.data = finder.company_name
        form.company_size.data = finder.company_size
        form.industry.data = finder.industry
        posts = ServicePost.query.filter_by(finder_id=current_user.id).order_by(ServicePost.created_at.desc()).limit(5).all()
        skills = []

    return render_template('professional_profile.html', 
                         form=form, 
                         skills=skills,
                         posts=posts,
                         user=current_user,
                         social=(json.loads(current_user.social_links) if current_user.social_links else {}),
                         portfolio_images=portfolio_images if current_user.role == 'provider' else [])

# Settings
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    from forms import SettingsForm
    form = SettingsForm()

    if form.validate_on_submit():
        # Update name
        current_user.name = form.name.data
        
        # Update password if provided
        if form.current_password.data:
            if check_password_hash(current_user.password, form.current_password.data):
                if form.new_password.data:
                    current_user.password = generate_password_hash(form.new_password.data)
                    flash('Password updated successfully!', 'success')
            else:
                flash('Current password is incorrect.', 'danger')
                return render_template('settings.html', form=form)

        # Update notification settings
        current_user.email_notifications = form.email_notifications.data

        # Update provider-specific settings
        if current_user.role == 'provider':
            current_user.provider.profile_visible = form.profile_visible.data

        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))

    # Pre-fill form
    form.name.data = current_user.name
    form.email.data = current_user.email
    form.email_notifications.data = current_user.email_notifications
    if current_user.role == 'provider':
        form.profile_visible.data = current_user.provider.profile_visible

    return render_template('settings.html', form=form)

# Delete account
@app.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    try:
        # Delete associated models first
        if current_user.role == 'provider':
            ProviderSkill.query.filter_by(provider_id=current_user.provider.id).delete()
            db.session.delete(current_user.provider)
        else:
            ServicePost.query.filter_by(finder_id=current_user.id).delete()
            db.session.delete(current_user.finder)

        # Delete profile image if exists
        if current_user.profile_image:
            try:
                filepath = os.path.join(app.root_path, 'static', current_user.profile_image)
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                print(f"Error removing profile image: {e}")

        # Delete user
        user_id = current_user.id
        logout_user()
        User.query.filter_by(id=user_id).delete()
        db.session.commit()
        flash('Your account has been deleted.', 'info')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting account. Please try again.', 'danger')
        print(f"Error deleting account: {e}")

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
    form.location.data = prov.location
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
        prov.location = form.location.data
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('provider_dashboard'))
    form.title.data = prov.title
    form.description.data = prov.description
    form.location.data = prov.location
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

# View matches (AI-powered)
@app.route('/post/<int:post_id>/matches')
@login_required
def view_matches(post_id):
    post = ServicePost.query.get_or_404(post_id)
    # Ensure only the finder who created this post can view it
    if current_user.role != 'finder' or post.finder_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    # find providers in DB and compute AI-based score
    providers = Provider.query.all()
    scored = gemini_match_providers(post, providers)
    top = [item[1] for item in scored[:10]]  # top 10
    return render_template('view_matches.html', post=post, matches=top, scored=scored[:10])

# View Profile
@app.route('/user/<int:user_id>')
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    # Prepare social links dict for template
    try:
        social = json.loads(user.social_links) if user.social_links else {}
    except Exception:
        social = {}

    if user.role == 'provider':
        skills = user.provider.skills if user.provider else []
        try:
            portfolio_images = json.loads(user.provider.portfolio_images) if user.provider and user.provider.portfolio_images else []
        except Exception:
            portfolio_images = []
        return render_template('view_profile.html', user=user, skills=skills, social=social, portfolio_images=portfolio_images)
    else:
        posts = []
        if current_user.is_authenticated and current_user.id == user.id:
            posts = ServicePost.query.filter_by(finder_id=user.id)\
                                  .order_by(ServicePost.created_at.desc())\
                                  .limit(5).all()
    return render_template('view_profile.html', user=user, posts=posts, social=social, portfolio_images=[])

# Finder profile
@app.route('/finder/profile', methods=['GET', 'POST'])
@login_required
def finder_profile():
    if current_user.role != 'finder':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    # Check if finder profile exists, create if not
    finder = current_user.finder
    if not finder:
        finder = Finder(user_id=current_user.id, bio='', location='')
        db.session.add(finder)
        db.session.commit()
    form = FinderProfileForm()
    if form.validate_on_submit():
        finder.bio = form.bio.data
        finder.location = form.location.data
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('finder_dashboard'))
    form.bio.data = finder.bio
    form.location.data = finder.location
    return render_template('finder_profile.html', finder=finder, form=form)

# Provider best matches (service posts)
@app.route('/provider/best-matches')
@login_required
def provider_best_matches():
    if current_user.role != 'provider':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    prov = current_user.provider
    # Get all open posts
    posts = ServicePost.query.filter_by(status='open').order_by(ServicePost.created_at.desc()).all()
    # Use Gemini AI to match posts
    scored = gemini_match_posts(prov, posts)
    top = [item[1] for item in scored[:10]]  # top 10
    return render_template('provider_best_matches.html', provider=prov, matches=top, scored=scored[:10])

# Run
if __name__ == '__main__':
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        # Auto-migration: Add new columns
        try:
            import sqlite3
            conn = sqlite3.connect('instance/servease.db')
            cursor = conn.cursor()

            # Check users table columns
            cursor.execute("PRAGMA table_info(users)")
            user_columns = [column[1] for column in cursor.fetchall()]
            
            # Add new columns to users table
            new_user_columns = {
                'profile_image': 'VARCHAR(200)',
                'cover_image': 'VARCHAR(200)',
                'tagline': 'VARCHAR(200)',
                'email_notifications': 'BOOLEAN DEFAULT 1',
                'phone': 'VARCHAR(20)',
                'website': 'VARCHAR(200)',
                'social_links': 'TEXT',
                'location': 'VARCHAR(200)'
            }
            
            for col_name, col_type in new_user_columns.items():
                if col_name not in user_columns:
                    cursor.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
                    print(f"✓ Added {col_name} column to users table")

            # Check providers table columns
            cursor.execute("PRAGMA table_info(providers)")
            provider_columns = [column[1] for column in cursor.fetchall()]
            
            # Add new columns to providers table
            new_provider_columns = {
                'location': 'VARCHAR(200)',
                'profile_visible': 'BOOLEAN DEFAULT 1',
                'business_name': 'VARCHAR(200)',
                'business_hours': 'TEXT',
                'experience_years': 'INTEGER',
                'certificates': 'TEXT',
                'service_areas': 'TEXT',
                'languages': 'TEXT',
                'hourly_rate': 'FLOAT',
                'portfolio_images': 'TEXT'
            }
            
            for col_name, col_type in new_provider_columns.items():
                if col_name not in provider_columns:
                    cursor.execute(f'ALTER TABLE providers ADD COLUMN {col_name} {col_type}')
                    print(f"✓ Added {col_name} column to providers table")

            # Add new columns to finders table
            cursor.execute("PRAGMA table_info(finders)")
            finder_columns = [column[1] for column in cursor.fetchall()]
            
            new_finder_columns = {
                'preferences': 'TEXT',
                'favorite_providers': 'TEXT',
                'company_name': 'VARCHAR(200)',
                'company_size': 'VARCHAR(50)',
                'industry': 'VARCHAR(100)'
            }
            
            for col_name, col_type in new_finder_columns.items():
                if col_name not in finder_columns:
                    cursor.execute(f'ALTER TABLE finders ADD COLUMN {col_name} {col_type}')
                    print(f"✓ Added {col_name} column to finders table")

            # Check if finders table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='finders'")
            if not cursor.fetchone():
                cursor.execute("""
                    CREATE TABLE finders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        bio TEXT,
                        location VARCHAR(200),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                """)
                print("✓ Created finders table")

            # Create profile_images directory if it doesn't exist
            profile_images_dir = os.path.join(app.root_path, 'static', 'profile_images')
            if not os.path.exists(profile_images_dir):
                os.makedirs(profile_images_dir)
                print("✓ Created profile_images directory")

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Migration note: {e}")
    
    app.run(debug=True)
