from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/registration')
def register():
    return render_template('customer_registration.html')

@app.route('/waiter_dashboard')
def waiter_dash():
    return render_template('waiter_dashboard.html')

@app.route('/sustomer_dashboard')
def cust_dash():
    return render_template('customer_dashboard.html')

@app.route('/chef_dashboard')
def chef_dash():
    return render_template('chef_dashboard.html')

if(__name__) == '__main__':
    app.run(debug=True)