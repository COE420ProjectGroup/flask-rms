from flask import render_template, Flask, request, redirect, url_for, make_response
from hashlib import md5, sha256
import cx_Oracle
from os import urandom
from datetime import datetime as dt

sessions = {}
app = Flask(__name__)

def getType(ck):
	global sessions
	if 'sessionID' not in ck.keys():
		return -1
	if ck['sessionID'] not in sessions.keys():
		return -1
	return sessions[ck['sessionID']].type
	

class User:
	def __init__(self, fn, ln):
		self.fname = fn
		self.lname = ln

class Employee(User):
	def __init__(self, fn, ln, uname, t):
		super().__init__(fn, ln)
		self.username = uname
		self.type = t

class Customer(User):
	def __init__(self, fn, ln, tcode, custID):
		super().__init__(fn, ln)
		self.tcode = tcode
		self.type = 3
		self.custID = custID




@app.route("/")
def index():
	return render_template("index.html")

@app.route("/customer")
def customer():
	global sessions
	if 'sessionID' in request.cookies:
		s = request.cookies['sessionID']
		if s in sessions:
			if sessions[s].type == 3:
				cust = sessions[s]
			else:
				return redirect(url_for('register'))
		else: # invalid sessionID cookie
			resp = redirect(url_for('register'))
			resp.set_cookie('sessionID', '', expires=0)
			return resp
	else:
		return redirect(url_for('register'))
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute("select rorders.ordernum, name, qty, addinfo from rorders, rorderdetails, rmenu where rorders.ordernum=rorderdetails.ordernum AND rorderdetails.itemid=rmenu.itemid AND custID="+str(cust.custID) + " order by rorders.ordernum")
	res = [row for row in res]
	ord = {}
	for row in res:
		ord.setdefault(row[0],[]).append(row)
	return render_template("customer_dashboard.html", user=cust, orders=ord)



@app.route("/dashboard")
def dashboard():
	global sessions
	if 'sessionID' in request.cookies:
		s = request.cookies['sessionID']
		if s in sessions:
			if sessions[s].type != 3:
				emp = sessions[s]
			else:
				return redirect(url_for('login'))
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
				if sessions[s].type != 3:
					return redirect(url_for('dashboard'))
				else:
					return render_template("login.html")
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
	global sessions
	if 'sessionID' in request.cookies:
			s = request.cookies['sessionID']
			if s in sessions:
				sessions.pop(s)
	resp = redirect(url_for('index'))
	resp.set_cookie('sessionID', '', expires=0)
	return resp

@app.route('/register', methods = ['GET', 'POST'])
def register():
	if request.method == 'GET':
		if 'sessionID' in request.cookies:
			s = request.cookies['sessionID']
			if s in sessions:
				if sessions[s].type == 3:
					return redirect(url_for('customer'))
				else:
					return render_template('customer_registration.html')
			else: # invalid sessionID cookie
				resp = make_response(render_template("customer_registration.html"))
				resp.set_cookie('sessionID', '', expires=0)
				return resp
		else:
			return render_template('customer_registration.html')
	# else POST
	fname = request.form['fname']
	lname = request.form['lname']
	tcode = request.form['tcode']
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute("select max(custID) from rcustomer")
	custID = int(list(res)[0][0]) + 1 # incr custID

	cur = connection.cursor()
	res = cur.execute("insert into rcustomer (custID, tablecode, fname, lname, paymentRequested) values ({},'{}','{}','{}',0)".format(custID,tcode, fname, lname))
	connection.commit()
	print(res)
	cust = Customer(fname, lname, tcode, custID)
	sessID = sha256(cust.fname.encode() + urandom(16)).hexdigest()
	sessions[sessID] = cust
	print(sessions)
	resp = redirect(url_for('customer'))
	resp.set_cookie('sessionID', sessID)
	return resp


@app.route("/place", methods = ['POST'])
def place():
	global sessions
	if getType(request.cookies) != 3:
		return redirect(url_for('index'))
	custID = sessions[request.cookies['sessionID']].custID
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute("select max(orderNum) from rorders")
	ordnum = int(list(res)[0][0]) + 1 # incr ordNum
	cur = connection.cursor()
	n = dt.now()
	res = cur.execute(f"insert into rorders (orderNum, custID, o_date, placed, prepared, delivered) values ({ordnum},{custID},TO_DATE('{n.day}/{n.month}/{n.year} {n.hour}:{n.minute}:{n.second}', 'dd/mm/yy hh24:mi:ss'), 1, 0, 0)")
	connection.commit()

	for itemID, qty in request.json.items():
		if qty != '0':
			cur = connection.cursor()
			#print(f"insert into rorderDetails values ({ordnum},{itemID[1:]},{qty},NULL)")
			res = cur.execute(f"insert into rorderDetails values ({ordnum},{itemID[1:]},{qty},NULL)")
			connection.commit()

	#print(request.json, request.cookies)
	return 'success'