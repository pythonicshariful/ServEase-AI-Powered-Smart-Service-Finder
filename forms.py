from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, PasswordField, SubmitField, TextAreaField,
    IntegerField, SelectField, BooleanField, MultipleFileField, FloatField
)
from wtforms.validators import DataRequired, Email, EqualTo, Optional, Length, NumberRange


class RegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), EqualTo('confirm', message='Passwords must match')])
    confirm = PasswordField('Repeat Password')
    role = SelectField('Role', choices=[('provider', 'Service Provider'), ('finder', 'Service Finder')], validators=[DataRequired()])
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class UserBaseProfileForm(FlaskForm):
    profile_image = FileField('Profile Image', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])
    cover_image = FileField('Cover Image', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])
    name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    tagline = StringField('Professional Tagline', validators=[Optional(), Length(max=200)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    website = StringField('Website', validators=[Optional(), Length(max=200)])
    location = StringField('Location', validators=[Optional(), Length(max=200)])
    facebook = StringField('Facebook Profile', validators=[Optional(), Length(max=200)])
    twitter = StringField('Twitter Profile', validators=[Optional(), Length(max=200)])
    linkedin = StringField('LinkedIn Profile', validators=[Optional(), Length(max=200)])


class ProviderProfileForm(UserBaseProfileForm):
    business_name = StringField('Business Name', validators=[Optional(), Length(max=200)])
    title = StringField('Professional Title', validators=[Optional(), Length(max=150)])
    description = TextAreaField('About Your Services', validators=[Optional()])
    experience_years = IntegerField('Years of Experience', validators=[Optional(), NumberRange(min=0, max=100)])
    hourly_rate = FloatField('Hourly Rate (BDT)', validators=[Optional(), NumberRange(min=0)])
    languages = StringField('Languages Spoken (comma-separated)', validators=[Optional()])
    certificates = TextAreaField('Certifications & Qualifications', validators=[Optional()])
    service_areas = TextAreaField('Service Coverage Areas (comma-separated)', validators=[Optional()])
    portfolio_images = MultipleFileField('Portfolio Images', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])
    business_hours = TextAreaField('Business Hours', validators=[Optional()])
    submit = SubmitField('Save Provider Profile')


class FinderProfileForm(UserBaseProfileForm):
    bio = TextAreaField('About You/Your Business', validators=[Optional()])
    company_name = StringField('Company Name', validators=[Optional(), Length(max=200)])
    company_size = SelectField('Company Size', choices=[
        ('', 'Select Size'),
        ('1-10', '1-10 employees'),
        ('11-50', '11-50 employees'),
        ('51-200', '51-200 employees'),
        ('201-1000', '201-1000 employees'),
        ('1000+', '1000+ employees')
    ], validators=[Optional()])
    industry = StringField('Industry Sector', validators=[Optional(), Length(max=100)])
    preferences = TextAreaField('Service Preferences & Requirements', validators=[Optional()])
    submit = SubmitField('Save Finder Profile')


class SettingsForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    current_password = PasswordField('Current Password', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[
        Optional(),
        EqualTo('confirm_password', message='Passwords must match')
    ])
    confirm_password = PasswordField('Confirm Password')
    email_notifications = BooleanField('Email Notifications')
    profile_visible = BooleanField('Profile Visibility')
    submit = SubmitField('Save Settings')


class SkillForm(FlaskForm):
    skill = StringField('Skill (e.g., Plumbing)', validators=[DataRequired()])
    proficiency = SelectField('Proficiency Level', choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('expert', 'Expert')
    ], validators=[DataRequired()])
    years_experience = IntegerField('Years of Experience', validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField('Add Skill')


class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    location = StringField('Location', validators=[Optional()])
    budget_min = IntegerField('Budget Min (BDT)', validators=[Optional()])
    budget_max = IntegerField('Budget Max (BDT)', validators=[Optional()])
    submit = SubmitField('Create Post')
