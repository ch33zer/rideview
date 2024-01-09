import os
import secrets
import requests
import datetime
import random
import polyline
from dataclasses import dataclass
from dotenv import load_dotenv
from flask import (
    Flask,
    redirect,
    url_for,
    render_template,
    flash,
    session,
    current_app,
    request,
    abort,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    current_user,
    login_required,
)
from urllib.parse import urlencode, quote_plus

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["OAUTH2_INFO"] = {
    "client_id": os.environ.get("STRAVA_CLIENT_ID"),
    "client_secret": os.environ.get("STRAVA_CLIENT_SECRET"),
    "authorize_url": "https://www.strava.com/oauth/authorize",
    "token_url": "https://www.strava.com/oauth/token",
    "scopes": ["activity:read"],
}

login = LoginManager(app)
login.login_view = "index"


@dataclass
class User(UserMixin):
    id: int
    token: str
    username: str

    def get_id(self):
        return self.id


MAX_POINT_SAMPLES = 10


@dataclass
class Activity:
    id: str
    name: str
    type: str
    summary_polyline: str

    @staticmethod
    def from_json(json):
        id = json.get("id")
        name = json.get("name")
        summary_polyline = json.get("map").get("summary_polyline")
        type = json.get("type")
        return Activity(id, name, type, summary_polyline)

    def sample_polyline(self):
        points = polyline.decode(self.summary_polyline)
        print("points", points)
        step = max(len(points) // MAX_POINT_SAMPLES, 1)
        print("Indexes", 0, len(points), step, list(range(0, len(points), step)))
        sampled = [points[i] for i in range(0, len(points), step)]
        print("sampled", sampled)
        return sampled


@login.user_loader
def load_user(id):
    if "token" not in session or "username" not in session:
        return None
    return User(id, session["token"], session["username"])


def get_activities(page):
    response = requests.get(
        f"https://www.strava.com/api/v3/athlete/activities?page={page}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {current_user.token}",
        },
    )
    if response.status_code != 200:
        flash("Failed to load activities.")
        return []
    ret = []
    json = response.json()
    for activity in json:
        ret.append(Activity.from_json(activity))
    return ret


def get_activity(id):
    response = requests.get(
        f"https://www.strava.com/api/v3/activities/{quote_plus(id)}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {current_user.token}",
        },
    )
    if response.status_code != 200:
        flash(f"Failed to load activity.")
        return None
    return Activity.from_json(response.json())


@app.route("/")
def index():
    activities = None
    page = None
    if not current_user.is_anonymous:
        page = request.args.get('page', 1, int)
        activities = get_activities(page)
    return render_template("index.html", activities=activities, page=page)


@app.route("/activity/<activity_id>")
@login_required
def activity(activity_id):
    activity = get_activity(activity_id)
    coordinate_str = ",".join(f"{lat},{lng}" for lat, lng in activity.sample_polyline())
    return render_template(
        "activity.html",
        activity=get_activity(activity_id),
        coordinate_str=coordinate_str,
    )


@app.route("/logout")
def logout():
    logout_user()
    session.pop("token", default=None)
    session.pop("username", default=None)
    flash("You have been logged out.")
    return redirect(url_for("index"))


@app.route("/authorize")
def oauth2_authorize():
    if not current_user.is_anonymous:
        return redirect(url_for("index"))

    provider_data = current_app.config["OAUTH2_INFO"]
    if provider_data is None:
        abort(404)

    # generate a random string for the state parameter
    session["oauth2_state"] = secrets.token_urlsafe(16)

    # create a query string with all the OAuth2 parameters
    qs = urlencode(
        {
            "client_id": provider_data["client_id"],
            "redirect_uri": url_for("oauth2_callback", _external=True),
            "response_type": "code",
            "scope": " ".join(provider_data["scopes"]),
            "state": session["oauth2_state"],
        }
    )

    # redirect the user to the OAuth2 provider authorization URL
    return redirect(provider_data["authorize_url"] + "?" + qs)


@app.route("/callback")
def oauth2_callback():
    if not current_user.is_anonymous:
        return redirect(url_for("index"))

    provider_data = current_app.config["OAUTH2_INFO"]
    if provider_data is None:
        abort(404)

    # if there was an authentication error, flash the error messages and exit
    if "error" in request.args:
        for k, v in request.args.items():
            if k.startswith("error"):
                flash(f"{k}: {v}")
        return redirect(url_for("index"))

    # make sure that the state parameter matches the one we created in the
    # authorization request
    if request.args["state"] != session.get("oauth2_state"):
        abort(401)

    # make sure that the authorization code is present
    if "code" not in request.args:
        abort(401)

    if "scope" not in request.args or "activity:read" not in request.args["scope"]:
        flash("You must accept the 'activity:read' permission to continue.")
        return redirect(url_for("index"))

    # exchange the authorization code for an access token
    response = requests.post(
        provider_data["token_url"],
        data={
            "client_id": provider_data["client_id"],
            "client_secret": provider_data["client_secret"],
            "code": request.args["code"],
            "grant_type": "authorization_code",
            "redirect_uri": url_for("oauth2_callback", _external=True),
        },
        headers={"Accept": "application/json"},
    )
    if response.status_code != 200:
        abort(401)

    response_json = response.json()
    oauth2_token = response_json.get("access_token")
    if not oauth2_token:
        abort(401)
    username = response_json.get("athlete").get("username")
    if not username:
        abort(401)
    session["token"] = oauth2_token
    session["username"] = username

    user = User(random.randint(1, 10000000), oauth2_token, username)

    login_user(user, duration=datetime.timedelta(hours=6))
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
