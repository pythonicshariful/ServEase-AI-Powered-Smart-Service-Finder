from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Optional

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

class ProviderProfileForm(FlaskForm):
    title = StringField('Title (e.g., Electrician, Plumber)', validators=[Optional()])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save Profile')

class SkillForm(FlaskForm):
    skill = StringField('Skill (e.g., Plumbing)', validators=[DataRequired()])
    submit = SubmitField('Add Skill')

class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    location = StringField('Location', validators=[Optional()])
    budget_min = IntegerField('Budget Min (BDT)', validators=[Optional()])
    budget_max = IntegerField('Budget Max (BDT)', validators=[Optional()])
    submit = SubmitField('Create Post')
