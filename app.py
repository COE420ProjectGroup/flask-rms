from flask import render_template, Flask, request, redirect, url_for, make_response
from hashlib import md5, sha256
import cx_Oracle
from os import urandom



class User:
	def __init__(self, fn, ln):
		self.fname = fn
		self.lname = ln

class Employee(User):
	def __init__(self, fn, ln, uname, t):
		super().__init__(fn, ln)
		self.username = uname
		self.type = t

sessions = {}


app = Flask(__name__)

@app.route("/")
def index():
	return render_template("index.html")

@app.route("/customer")
def customer():
	custId = 0
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute("select rorders.ordernum, name, qty, addinfo from rorders, rorderdetails, rmenu where rorders.ordernum=rorderdetails.ordernum AND rorderdetails.itemid=rmenu.itemid AND custID="+str(custId) + " order by rorders.ordernum")
	res = [row for row in res]
	ord = {}
	for row in res:
		ord.setdefault(row[0],[]).append(row)
	return render_template("customer_dashboard.html", orders=ord)



@app.route("/dashboard")
def dashboard():
	global sessions
	if 'sessionID' in request.cookies:
		s = request.cookies['sessionID']
		if s in sessions:
			emp = sessions[s]
		else: # invalid sessionID cookie
			resp = redirect(url_for('login'))
			resp.set_cookie('sessionID', '', expires=0)
			return resp
	else:
		return redirect(url_for('login'))
	if emp.type == 0:
		return render_template("manager_dashboard.html", user=emp, bookedTables=[1,3,7,8])
	elif emp.type == 1:
		return render_template("waiter_dashboard.html", user=emp, bookedTables=[1,3,7,8])
	elif emp.type == 2:
		return render_template("chef_dashboard.html", user=emp, bookedTables=[1,3,7,8])
	else:
		assert False



@app.route("/login", methods = ['GET','POST'])
def login():
	global sessions

	if request.method == 'GET':
		if 'sessionID' in request.cookies:
			s = request.cookies['sessionID']
			if s in sessions:
				return redirect(url_for('dashboard'))
			else: # invalid sessionID cookie
				resp = make_response(render_template("login.html"))
				resp.set_cookie('sessionID', '', expires=0)
				return resp
		else:
			return render_template("login.html")
	
	# else: request.method=='POST'
	user = request.form['user']
	pwd = md5(request.form['pass'].encode()).hexdigest()
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute("select Fname, Lname, username, type from REmployeeAccounts where username='{}' and password='{}'".format(user, pwd))
	res = [row for row in res]
	if len(res) > 0:
		emp = Employee(*res[0])
		sessID = sha256(emp.username.encode() + urandom(16)).hexdigest()
		sessions[sessID] = emp
		print(sessions)
		resp = redirect(url_for('dashboard'))
		resp.set_cookie('sessionID', sessID)
		return resp
	else:
		return 'pls no hax'


@app.route("/logout", methods = ['GET'])
def logout():
	resp = redirect(url_for('index'))
	resp.set_cookie('sessionID', '', expires=0)
	return resp

@app.route('/register')
def register():
    return render_template('customer_registration.html')