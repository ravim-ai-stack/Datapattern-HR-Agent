"""HTML pages for the four-step letter workflow."""

from flask import Blueprint, redirect, render_template

from src.constants.constants import LETTER_TYPES
from src.settings.settings import settings

page_bp = Blueprint("pages", __name__)


@page_bp.route("/")
def index():
    return redirect("/step1")


@page_bp.route("/step1")
def step1():
    return render_template("step1.html", active_step=1, letter_types=LETTER_TYPES)


@page_bp.route("/hr-studio")
def hr_studio():
    return render_template("hr_studio.html")


@page_bp.route("/step2")
def step2():
    return render_template("step2.html", active_step=2)


@page_bp.route("/step3")
def step3():
    return render_template("step3.html", active_step=3)


@page_bp.route("/step4")
def step4():
    return render_template("step4.html", active_step=4, sender_email=settings.system_sender_email)
