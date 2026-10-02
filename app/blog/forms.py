from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class BlogPostForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    slug = StringField(
        "URL slug (leave blank to auto-generate from title)",
        validators=[Optional(), Length(max=220)],
    )
    excerpt = StringField(
        "Short excerpt (shown in the blog list and search results, ~1-2 sentences)",
        validators=[Optional(), Length(max=300)],
    )
    body_markdown = TextAreaField(
        "Body (Markdown supported — # heading, **bold**, - list, [text](url) links)",
        validators=[DataRequired()],
    )
    is_published = BooleanField("Published (uncheck to save as a draft)", default=True)
    submit = SubmitField("Save post")
