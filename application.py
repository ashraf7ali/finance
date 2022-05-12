import os
import time

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    ROWS = db.execute("""SELECT symbol, sum(price * shares) as value, sum(shares) as\n
    shares FROM transactions WHERE user_id = ? GROUP BY symbol""", session['user_id'])
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])
    # changing idea to get symbol and its total here
    # make a table with requerd data and pass it to html to display
    # print(ROWS)
    total = []
    for row in ROWS:
        look = lookup(row['symbol'])
        row['name'] = look['name']
        row['price'] = look['price']
        total.append(row['value'])
    # print(cash)
    return render_template("index.html", rows=ROWS, cash=cash[0]['cash'], total=sum(total) + cash[0]['cash'])


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol or not shares:
            return apology("Enter valid inputs", 400)
        if shares.isdigit():
            shares = int(shares)
        else:
            return apology("Enter valid shares", 400)
        look = lookup(symbol)
        if look == None:
                return apology("Invalid symbol", 400)
        price = look["price"]
        # get available cash with user
        money = db.execute("SELECT cash FROM users WHERE id is ?", session['user_id'])
        cash = money[0]['cash']
        shares = int(shares)
        timenow = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        if cash > shares*price:
            cash = cash - shares*price
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session['user_id'])
            db.execute("""INSERT INTO transactions(symbol, price, shares, type, time, user_id) \n
            VALUES (?,?,?,?,?,?)""", symbol.upper(), price, shares, "Buy", timenow, session['user_id'])
            return redirect('/')
        else:
            return apology("Not enaough funds", 400)

        # db.execute("INSERT INTO share (username, symbol, share) VALUES(?,?,?)", username, sybol,shares)

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    ROWS = db.execute("SELECT symbol,  shares, price, time FROM transactions WHERE user_id = ?", session['user_id'])

    # print(ROWS)
    return render_template("history.html", rows=ROWS)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Enert valid symbol", 400)
        look = lookup(symbol)

        if look == None:
                return apology("Invalid symbol", 400)
        return render_template("quoted.html", look=lookup(symbol))

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # print(username, password, confirmation)
        if not username:
            return apology("must provide username", 400)
        if not password or not confirmation:
            return apology("must provide password", 400)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Password dosen't match", 400)
        query = db.execute("SELECT username FROM users WHERE username = ?", username)
        if len(query) > 0:
            if query[0]['username'] != None:
                return apology("User Already Exists", 400)
        db.execute("INSERT INTO users (username , hash) VALUES (? , ?)", username, generate_password_hash(password))

        return redirect("/login")
    else:
        return render_template("register.html")

    return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        share_dict = db.execute("""SELECT sum(shares) as quantity FROM transactions\n
        WHERE user_id = ? AND symbol = ?""", session['user_id'], symbol)
        share_owned = share_dict[0]['quantity']
        if share_owned < shares or shares < 1:
            return apology("Not enough Shares to sell")

        price = lookup(symbol)["price"]

        money = db.execute("SELECT cash FROM users WHERE id is ?", session['user_id'])
        cash = money[0]['cash']
        cash = cash + shares*price

        timenow = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session['user_id'])
        db.execute("""INSERT INTO transactions(symbol, price, shares, type, time, user_id) \n
        VALUES (?,?,?,?,?,?)""", symbol.upper(), price, -1*shares, "Sell", timenow, session['user_id'])

        return redirect('/')

    else:
        ROWS = db.execute("SELECT DISTINCT symbol FROM transactions WHERE user_id = ?", session['user_id'])
        # print(ROWS)
        return render_template("sell.html", rows=ROWS)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
