from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class RegistrationForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=80)],
    )
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email()],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8)],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    invite_code = StringField(
        "Invite Code",
        validators=[DataRequired()],
    )
    submit = SubmitField("Register")


class LoginForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email()],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired()],
    )
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Log In")
