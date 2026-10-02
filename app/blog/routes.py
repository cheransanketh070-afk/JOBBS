import re
import markdown
from flask import Blueprint, render_template, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import BlogPost
from app.blog.forms import BlogPostForm

blog_bp = Blueprint("blog", __name__, url_prefix="/blog")


def _is_admin() -> bool:
    if not current_user.is_authenticated:
        return False
    admins = current_app.config.get("ADMIN_EMAILS", set())
    return current_user.email.lower() in admins


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:220] or "post"


def _unique_slug(base_slug: str, ignore_id: int = None) -> str:
    slug = base_slug
    n = 2
    while True:
        query = BlogPost.query.filter_by(slug=slug)
        if ignore_id:
            query = query.filter(BlogPost.id != ignore_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{n}"
        n += 1


@blog_bp.route("/")
def list_posts():
    posts = BlogPost.query.filter_by(is_published=True).order_by(BlogPost.created_at.desc()).all()
    return render_template("blog/list.html", posts=posts)


@blog_bp.route("/<slug>")
def view_post(slug):
    post = BlogPost.query.filter_by(slug=slug).first()
    if not post:
        abort(404)
    if not post.is_published and not _is_admin():
        abort(404)
    html = markdown.markdown(post.body_markdown, extensions=["extra", "sane_lists"])
    return render_template("blog/detail.html", post=post, body_html=html)


@blog_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_post():
    if not _is_admin():
        abort(403)

    form = BlogPostForm()
    if form.validate_on_submit():
        base_slug = _slugify(form.slug.data or form.title.data)
        slug = _unique_slug(base_slug)
        post = BlogPost(
            title=form.title.data.strip(),
            slug=slug,
            excerpt=(form.excerpt.data or "").strip() or None,
            body_markdown=form.body_markdown.data,
            is_published=form.is_published.data,
            author_id=current_user.id,
        )
        db.session.add(post)
        db.session.commit()
        flash("Post saved.", "success")
        return redirect(url_for("blog.view_post", slug=post.slug))

    return render_template("blog/form.html", form=form, mode="new")


@blog_bp.route("/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit_post(slug):
    if not _is_admin():
        abort(403)

    post = BlogPost.query.filter_by(slug=slug).first()
    if not post:
        abort(404)

    form = BlogPostForm(obj=post)
    if form.validate_on_submit():
        base_slug = _slugify(form.slug.data or form.title.data)
        post.slug = _unique_slug(base_slug, ignore_id=post.id)
        post.title = form.title.data.strip()
        post.excerpt = (form.excerpt.data or "").strip() or None
        post.body_markdown = form.body_markdown.data
        post.is_published = form.is_published.data
        db.session.commit()
        flash("Post updated.", "success")
        return redirect(url_for("blog.view_post", slug=post.slug))

    if request_is_get(form):
        form.slug.data = post.slug

    return render_template("blog/form.html", form=form, mode="edit", post=post)


def request_is_get(form) -> bool:
    # populated via obj=post on GET; avoid overwriting user input on failed POST validation
    from flask import request
    return request.method == "GET"
