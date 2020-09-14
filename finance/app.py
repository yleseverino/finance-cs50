import os


from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for, Response
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

import matplotlib.pyplot as plt

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
# if not os.environ.get("API_KEY"):
#     raise RuntimeError("API_KEY not set")

sucessful = [] #Variable to pass messages

port = int(os.getenv("PORT", 9099))

@app.route("/")
@login_required
def index():
    msg = ''
    if len(sucessful) == 1:
        msg = sucessful.pop()
    
    stocks = db.execute("SELECT * FROM stocks WHERE ? = PersonID",str(session["user_id"]))
    cash = db.execute("SELECT cash FROM users WHERE (id = :id)", id=str(session["user_id"]))

    total = 0

    for row in stocks:
        total += float(row['total'])
    
    total += float(cash[0]['cash'])

    return render_template('home.html', sucessful=msg, rows=stocks, cash=round(cash[0]['cash'],2), total=round(total,2))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    
    else:
        n = float(request.form.get("number"))
        stock = request.form.get("buy").lower()
        
        quote = lookup(stock)

        price = float(quote['price'])

        price = n * price

        wallet = db.execute("SELECT cash FROM users WHERE (id = :id)", id=str(session["user_id"]))

        if price > float(wallet[0]['cash']):
            return render_template("buy.html",noneresp=f"Not enough money price ${price} and wallet ${wallet[0]['cash']}")
        
        NewWallet = float(wallet[0]['cash']) - price

        db.execute("UPDATE users SET cash = :cash WHERE id = :id",
        id=str(session["user_id"]),
        cash=NewWallet
        )

        
        # Test if already exist that stock in your wallet
        old_shares = db.execute("SELECT shares, total FROM stocks WHERE symbol = ? AND PersonId = ?", stock.upper(),str(session["user_id"]))

        if not old_shares:
            db.execute("INSERT INTO stocks (PersonId, symbol, name, shares, price, total) VALUES (:PersonId, :symbol, :name, :shares, :price, :total)",
            PersonId=str(session["user_id"]),
            symbol=stock.upper(),
            name=quote['name'],
            shares=n,
            price=float(quote['price']),
            total=price
            )
        else:
            db.execute("UPDATE stocks SET PersonId = :PersonId, name = :name, shares = :shares, price = :price, total = :total WHERE (symbol = :symbol)",
            PersonId=str(session["user_id"]),
            symbol=stock.upper(),
            name=quote['name'],
            shares=n + int(old_shares[0]['shares']),
            price=float(quote['price']),
            total=price + int(old_shares[0]['total'])
            )

        # Update history
        db.execute("INSERT INTO transactions (PersonId, symbol, name, shares) VALUES (:PersonId, :symbol, :name, :shares)",
        PersonId=str(session["user_id"]),
        symbol=stock.upper(),
        name=quote['name'],
        shares=n
        )

        sucessful.append(f"bought {int(n)} share of {quote['name']} for ${round(price,2)} sucessful")

        return redirect('/')


@app.route("/history")
@login_required
def history():
    transactions = db.execute("SELECT * FROM transactions WHERE PersonId = ? ORDER BY Timestamp DESC LIMIT 30", session["user_id"])
    
    labels = []
    data = []
    
    for row in transactions:
        data.append(row['shares'])
        labels.append(row['Timestamp'])
    
    

    fig, ax = plt.subplots(figsize=(1300,250))
    
    ax.bar(labels, data)
    ax.set_ylabel('Nuber of shares')
    ax.set_ylabel('History')
    ax.set_axis_off()
    fig.savefig('static/plot.svg')
    


    return render_template("history.html", rows = transactions)



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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
    if request.method == "GET":
        return render_template("quote.html")
    quote = lookup(request.form.get("quote").lower())
        
    if quote == None:
        return render_template("quote.html", noneresp="Not found ")

    return render_template("quote.html", quote=quote['price'], name=quote['name'], symbol=quote['symbol'])


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        db.execute("INSERT INTO users (username, hash)  VALUES (:username, :hash)",
                          username = request.form.get("username"),
                          hash = generate_password_hash(request.form.get("password"), "sha256")
                          )

        # Redirect to login page
        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    if request.method == "GET":
        return render_template("sell.html")

    n = float(request.form.get("number"))
    stock = request.form.get("sell")

    # check the number of stocks in wallet
    n_real = db.execute("SELECT shares FROM stocks WHERE PersonId = ? AND symbol = ?",
    str(session["user_id"]),
    stock,
    )

    if not n_real:
        return render_template("sell.html",noneresp=f"Not have shares of {stock}")

    n_total = int(n_real[0]['shares'])
    
    if n > n_total:
        return render_template("sell.html",noneresp=f"Not enough shares! you have {n_total} of {stock}")
    
    # Update wallet
    quote = lookup(request.form.get("sell").lower())

    if not quote:
        return render_template("sell.html",noneresp=f"{stock} not found")
    
    money_sell = float(quote['price']) * float(n)

    wallet = db.execute("SELECT cash FROM users WHERE id = ?", str(session["user_id"]))

    NewWallet = float(wallet[0]['cash']) + money_sell

    db.execute("UPDATE users SET cash = :cash WHERE id = :id",
        id=str(session["user_id"]),
        cash=NewWallet
    )

    # Update number of shares
    n_final = n_total - n

    if n_final == 0:
        db.execute("DELETE FROM stocks WHERE symbol = ?", stock)

    else:
        db.execute("UPDATE stocks SET shares = :shares, price = :price, total = :total WHERE PersonId = :id AND symbol = :symbol",
        id=str(session["user_id"]),
        symbol=stock,
        shares=n_final,
        price=quote['price'],
        total = n_final*float(quote['price'])
        )
    
    # Update history
    db.execute("INSERT INTO transactions (PersonId, symbol, name, shares) VALUES (:PersonId, :symbol, :name, :shares)",
    PersonId=str(session["user_id"]),
    symbol=stock.upper(),
    name=quote['name'],
    shares=-n
    )

    sucessful.append(f"Sold {int(n)} share of {quote['name']} for ${round(float(quote['price']),2)}")

    return redirect('/') 


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
