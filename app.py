import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)

app = Flask(__name__, template_folder='.')
app.secret_key = os.getenv("SECRET_KEY", "change-me-in-prod")

USERNAME = os.getenv("APP_USERNAME", "admin")
PASSWORD = os.getenv("APP_PASSWORD", "pass123")


@app.route("/", methods=["GET"])
def web():
    is_authed = session.get("is_authed", False)
    return render_template("index.html", is_authed=is_authed)


@app.route("/login", methods=["POST"])
def login():
    login_val = request.form.get("login", "")
    password_val = request.form.get("password", "")
    if login_val == USERNAME and password_val == PASSWORD:
        session["is_authed"] = True
        flash("Успешный вход", "success")
        return redirect(url_for("web"))
    flash("Неверный логин или пароль", "error")
    return redirect(url_for("web"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Вы вышли из системы", "info")
    return redirect(url_for("web"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)