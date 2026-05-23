from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, SubmitField
from wtforms.validators import InputRequired, NumberRange


class PredictionForm(FlaskForm):
    home_score = IntegerField(
        "Home Score",
        validators=[InputRequired(message="Required."), NumberRange(min=0, max=99)],
    )
    away_score = IntegerField(
        "Away Score",
        validators=[InputRequired(message="Required."), NumberRange(min=0, max=99)],
    )
    submit = SubmitField("Save Prediction")


class ChampionForm(FlaskForm):
    champion_team_id = SelectField(
        "Champion",
        coerce=int,
        validators=[InputRequired()],
    )
    submit = SubmitField("Save Champion Pick")
