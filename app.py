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

class MenuItem:
	def __init__(self, i, nm, dsc, pr, t, a):
		self.id = i
		self.name = nm
		self.desc = dsc
		self.price = pr
		self.type = t
		self.avail = a
	def __repr__(self):
		return f'Menu({self.name}, {self.desc}, {self.price}, {self.type}, {self.avail})'

class OrderItem:
	def __init__(self, name, qty, addinfo):
		self.name = name
		self.qty = qty
		self.addinfo = addinfo
	def __repr__(self):
		return f'OrderItem({self.name}, {self.qty}, {self.addinfo})'

class Order:
	def __init__(self, ordNum=-1, date=-1):
		self.ordNum = ordNum
		self.items = []
		self.date = date
		self.prepared = -1
		self.delivered = -1
	def __repr__(self):
		return f'Order({self.ordNum}, {self.items}, {self.date}, {self.prepared}, {self.delivered})'


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
	res = cur.execute("select * from rmenu order by type desc")
	items = [MenuItem(*i) for i in res]
	#print(items)
	custID = sessions[request.cookies['sessionID']].custID
	cur = connection.cursor()
	res = cur.execute(f"select rorders.ordernum, name, qty, addinfo, o_date, prepared, delivered from rorders, rorderdetails, rmenu where rorders.ordernum=rorderdetails.ordernum AND rorderdetails.itemid=rmenu.itemid AND custID = {custID} order by o_date")
	res = list(res)
	my_orders = {}
	for i in {o[0] for o in res}:
			my_orders[i] = Order()
	for r in res:
		my_orders[r[0]].ordNum = r[0]
		my_orders[r[0]].items.append(OrderItem(r[1],r[2],r[3]))
		my_orders[r[0]].date = r[4]
		my_orders[r[0]].prepared = int(r[5])
		my_orders[r[0]].delivered = int(r[6])
	#print(my_orders)
	return render_template("customer_dashboard.html", user=cust, my_orders=my_orders, menu=items)



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
		connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
		cur = connection.cursor()
		employeeAccounts = cur.execute("select fname, lname, username, email, type from remployeeaccounts")
		employeeAccounts = list(employeeAccounts)
		return render_template("manager_dashboard.html", user=emp, employeeAccounts=employeeAccounts)
	elif emp.type == 1:
		connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
		cur = connection.cursor()
		res = cur.execute("select rorders.ordernum, name, qty, addinfo, o_date from rorders, rorderdetails, rmenu where rorders.ordernum=rorderdetails.ordernum AND rorderdetails.itemid=rmenu.itemid AND placed = 1 AND prepared = 1  AND delivered = 0  AND waiter_picked_up is NULL order by o_date")
		res = list(res)
		prep_orders = {}
		for i in {o[0] for o in res}:
				prep_orders[i] = Order()
		for r in res:
			prep_orders[r[0]].ordNum = r[0]
			prep_orders[r[0]].items.append(OrderItem(r[1],r[2],r[3]))
			prep_orders[r[0]].date = r[4]

		cur = connection.cursor()
		res = cur.execute(f"select rorders.ordernum, name, qty, addinfo, o_date from rorders, rorderdetails, rmenu where rorders.ordernum=rorderdetails.ordernum AND rorderdetails.itemid=rmenu.itemid AND placed = 1 AND prepared = 1  AND delivered = 0  AND waiter_picked_up = '{emp.username}' order by o_date")
		res = list(res)
		my_orders = {}
		for i in {o[0] for o in res}:
				my_orders[i] = Order()
		for r in res:
			my_orders[r[0]].ordNum = r[0]
			my_orders[r[0]].items.append(OrderItem(r[1],r[2],r[3]))
			my_orders[r[0]].date = r[4]
		cur = connection.cursor()
		res = cur.execute("select tablecode from rcustomer where tablecode is not null and paymentCompletedBy is NULL")
		bookedTables = [r[0] for r in res]
		return render_template("waiter_dashboard.html", user=emp, bookedTables=bookedTables, prep_orders=prep_orders, my_orders=my_orders)
	elif emp.type == 2:
		connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
		cur = connection.cursor()
		res = cur.execute("select rorders.ordernum, name, qty, addinfo, o_date from rorders, rorderdetails, rmenu where rorders.ordernum=rorderdetails.ordernum AND rorderdetails.itemid=rmenu.itemid AND placed = 1 AND prepared = 0  AND delivered = 0  AND chef_picked_up is NULL order by o_date")
		res = list(res)
		all_orders = {}
		for i in {o[0] for o in res}:
				all_orders[i] = Order()
		for r in res:
			all_orders[r[0]].ordNum = r[0]
			all_orders[r[0]].items.append(OrderItem(r[1],r[2],r[3]))
			all_orders[r[0]].date = r[4]

		#print(all_orders)

		cur = connection.cursor()
		res = cur.execute(f"select rorders.ordernum, name, qty, addinfo, o_date from rorders, rorderdetails, rmenu where rorders.ordernum=rorderdetails.ordernum AND rorderdetails.itemid=rmenu.itemid AND placed = 1 AND prepared = 0  AND delivered = 0  AND chef_picked_up = '{emp.username}' order by o_date")
		res = list(res)
		my_orders = {}
		for i in {o[0] for o in res}:
				my_orders[i] = Order()
		for r in res:
			my_orders[r[0]].ordNum = r[0]
			my_orders[r[0]].items.append(OrderItem(r[1],r[2],r[3]))
			my_orders[r[0]].date = r[4]
		
		#print(my_orders)
		cur = connection.cursor()
		res = cur.execute("select tablecode from rcustomer where tablecode is not null and paymentCompletedBy is NULL")
		bookedTables = [r[0] for r in res]
		return render_template("chef_dashboard.html", user=emp, bookedTables=bookedTables, all_orders=all_orders, my_orders=my_orders)

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
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute("select tablecode from rcustomer where tablecode is not null and paymentCompletedBy is NULL")
	bookedTables = [r[0] for r in res]
	vacantTables = (set(range(1,11)) - set(bookedTables))
	if request.method == 'GET':
		if 'sessionID' in request.cookies:
			s = request.cookies['sessionID']
			if s in sessions:
				if sessions[s].type == 3:
					return redirect(url_for('customer'))
				else:
					return render_template('customer_registration.html', vacantTables=vacantTables)
			else: # invalid sessionID cookie
				resp = make_response(render_template("customer_registration.html", vacantTables=vacantTables))
				resp.set_cookie('sessionID', '', expires=0)
				return resp
		else:
			# print(vacantTables)
			return render_template('customer_registration.html', vacantTables=vacantTables)
	# else POST
	fname = request.form['fname']
	lname = request.form['lname']
	tcode = request.form['tcode']
	cur = connection.cursor()
	res = cur.execute("select max(custID) from rcustomer")
	custID = int(list(res)[0][0]) + 1 # incr custID

	cur = connection.cursor()
	res = cur.execute("insert into rcustomer (custID, tablecode, fname, lname, paymentRequested) values ({}, {},'{}','{}',0)".format(custID, tcode, fname, lname))
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

	for itemID, item in request.json.items():
		if item['qty'] != '0':
			qty, addinfo = item.values()
			cur = connection.cursor()
			# print(f"insert into rorderDetails values ({ordnum},{itemID[1:]},{qty},{addinfo})")
			res = cur.execute(f"insert into rorderDetails values ({ordnum},{itemID[1:]},{qty},'{addinfo}')")
			connection.commit()

	#print(request.json, request.cookies)
	return 'success'

@app.route("/prepare", methods = ['POST'])
def prepare():
	global sessions
	if getType(request.cookies) != 2:
		return redirect(url_for('index'))
	
	chefUsername = sessions[request.cookies['sessionID']].username
	#print(request.json)
	orderNum = int(request.json['ordNum'])
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute(f"update rorders set chef_picked_up = '{chefUsername}' where orderNum={orderNum}")
	connection.commit()
	return 'success'


@app.route("/complete", methods = ['POST'])
def complete():
	global sessions
	if getType(request.cookies) != 2:
		return redirect(url_for('index'))
	
	#print(request.json)
	orderNum = int(request.json['ordNum'])
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute(f"update rorders set prepared = 1 where orderNum={orderNum}")
	#print(len(res))
	connection.commit()
	return 'success'

@app.route("/collect", methods= ['POST'])
def collect():
	print(request.json)
	global sessions
	if getType(request.cookies) != 1:
		return redirect(url_for('index'))
	
	waiterUsername = sessions[request.cookies['sessionID']].username
	print(request.json)
	orderNum = int(request.json['ordNum'])
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute(f"update rorders set waiter_picked_up = '{waiterUsername}' where orderNum={orderNum}")
	connection.commit()
	return 'success'

@app.route("/deliver", methods = ['POST'])
def deliver():
	global sessions
	if getType(request.cookies) != 1:
		return redirect(url_for('index'))
	
	#print(request.json)
	orderNum = int(request.json['ordNum'])
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute(f"update rorders set delivered = 1 where orderNum={orderNum}")
	connection.commit()
	return 'success'

@app.route("/addEmployee", methods = ['POST'])
def addEmployee():
	print(request.json)
	print("123")
	""" fname = request.form['fname']
	lname = request.form['lname']
	userName = request.form['uname']
	pwd = md5(request.form['pwd'].encode()).hexdigest()
	email = request.form['email']
	userType = request.form['userType']
	if userType=="Chef" :
		userType = 2
	elif userType=="Waiter" :
		userType = 1
	else:
		userType = 0
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute("insert into remployeeaccounts (fname, lname, username, password, email, type) values ('{}','{}','{}','{}','{}',{})".format(fname, lname, userName, pwd, email, userType))
	connection.commit() """
	return 'success'

@app.route("/delEmployee", methods = ['POST'])
def delEmployee():
	username = str(request.json['username'])
	connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
	cur = connection.cursor()
	res = cur.execute(f"delete from remployeeaccounts where username='{username}'")
	connection.commit()
	return 'success'