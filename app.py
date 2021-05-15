from flask import render_template, Flask, request, redirect, url_for, make_response
from hashlib import md5, sha256
import cx_Oracle
from os import urandom
from datetime import datetime as dt
import datetime
import urllib
import requests
import json
import plotly

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
    def __init__(self, name, qty, addinfo, price = -1):
        self.name = name
        self.qty = qty
        self.addinfo = addinfo
        self.price = price
    def __repr__(self):
        return f'OrderItem({self.name}, {self.qty}, {self.addinfo})'

class Order:
    def __init__(self, ordNum=-1, date=-1):
        self.ordNum = ordNum
        self.items = []
        self.date = date
        self.prepared = -1
        self.delivered = -1
    def total(self):
        return sum([item.qty * item.price for item in self.items])
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
    res = cur.execute("select * from rmenu where avail = 1 order by type desc")
    items = [MenuItem(*i) for i in res]
    #print(items)
    custID = sessions[request.cookies['sessionID']].custID
    cur = connection.cursor()
    res = cur.execute(f"select rorders.ordernum, name, qty, addinfo, o_date, prepared, delivered, price from rorders, rorderdetails, rmenu where rorders.ordernum=rorderdetails.ordernum AND rorderdetails.itemid=rmenu.itemid AND custID = {custID} order by o_date")
    res = list(res)
    my_orders = {}
    for i in {o[0] for o in res}:
            my_orders[i] = Order()
    for r in res:
        my_orders[r[0]].ordNum = r[0]
        my_orders[r[0]].items.append(OrderItem(r[1],r[2],r[3],r[7]))
        my_orders[r[0]].date = r[4]
        my_orders[r[0]].prepared = int(r[5])
        my_orders[r[0]].delivered = int(r[6])
    #print(my_orders)
    return render_template("customer_dashboard.html", user=cust, my_orders=my_orders, menu=items, subtotal=sum(order.total() for order in my_orders.values()))



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
        cur = connection.cursor()
        res = cur.execute("select tablecode from rcustomer where tablecode is not null and paymentCompletedBy is NULL")
        bookedTables = [r[0] for r in res]
        cur = connection.cursor()
        res = cur.execute("select * from rmenu")
        menu = [MenuItem(*i) for i in res]
        query = ("select ord.o_date, sum(det.qty * mn.price) "
        "from RORDERDETAILS det, RORDERS ord, RMENU mn "
        "where ord.o_date between SYSDATE-7 and SYSDATE "
        "and det.ordernum = ord.ordernum "
        "and det.itemid = mn.itemid "
        "group by ord.o_date")
        res = cur.execute(query)
        saleshistory = dict([(date.strftime("%d %B, %Y"), amount) for date, amount in list(res)])
        dates = [(dt.today() - datetime.timedelta(days = day)).strftime("%d %B, %Y") for day in range(7)][::-1]
        # datevalueavailable = [date for date, s in saleshistory]
        sales = [saleshistory[d] if d in saleshistory.keys() else 0 for d in dates]
        graphs = dict(
            data=[
                dict(
                    x=dates,
                    y=sales,
                    marker = dict(color=['rgb(127, 15, 255)',]*7),
                    type='bar'
                ),
            ],
            layout=dict(
                title='This week\'s Sales',
                autosize=True
            )
        )
        graphJSON = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)
        res = cur.execute('select count(*) from rorders where trunc(o_date) = trunc(sysdate)')
        todayorders = list(res)[0][0]
        res = cur.execute("select mn.name, sum(det.qty) from rorderdetails det, rmenu mn where mn.itemid = det.itemid group by mn.name")
        ordered = dict(res)
        return render_template("manager_dashboard.html", user=emp, employeeAccounts=employeeAccounts, bookedTables=bookedTables,menu=menu, todaysales=sales[-1], graphJSON=graphJSON, todayorders=todayorders, mostordered=max(ordered, key=ordered.get))
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
        cur = connection.cursor()
        res = cur.execute("select tablecode from rcustomer where tablecode is not null and paymentCompletedBy is NULL and paymentRequested=1")
        payReq = [r[0] for r in res]
        return render_template("waiter_dashboard.html", user=emp, bookedTables=bookedTables, prep_orders=prep_orders, my_orders=my_orders, payReq=payReq)
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

@app.route("/requestPayment", methods = ['POST'])
def requestPayment():
    global sessions
    if getType(request.cookies) != 3:
        return redirect(url_for('index'))

    custID = sessions[request.cookies['sessionID']].custID
    connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
    cur = connection.cursor()
    res = cur.execute(f"update rcustomer set paymentRequested=1 where custID = {custID}")
    connection.commit()
    cur = connection.cursor()
    res = cur.execute(f"select fname from remployeeaccounts where username in (select paymentCompletedBy from rcustomer where custID = {custID})")
    waiter = None
    try:
        waiter = list(res)[0][0]
    except IndexError:
        waiter = None
    qrdata = f"{{'custID': '{custID}', 'confirmationCode': 'YupTheyReallyPaid',  'source': 'Just ask {waiter}'}}" if waiter else None
    return (f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote_plus(qrdata)}&color=7f0fff", 200) if waiter else ('None', 401)


@app.route("/pay", methods = ['POST'])
def pay():
    global sessions
    if getType(request.cookies) != 3:
        return redirect(url_for('index'))

    custID = sessions[request.cookies['sessionID']].custID
    connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
    cur = connection.cursor()
    res = cur.execute(f"update rcustomer set paymentCompletedBy = 'm1' where custID = {custID}") # pay by cc -> completed by manager
    connection.commit()
    qrdata = f"{{'custID': '{custID}', 'confirmationCode': 'YupTheyReallyPaid',  'source': 'Dude trust me'}}"
    return f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote_plus(qrdata)}&color=7f0fff"

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

@app.route("/attend", methods = ['POST'])
def attend():
    global sessions
    if getType(request.cookies) != 1:
        return redirect(url_for('index'))
    
    #print(request.json)
    waiterUsername = sessions[request.cookies['sessionID']].username
    tableCode = int(request.json['tableCode'])
    connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
    cur = connection.cursor()
    res = cur.execute(f"update rcustomer set paymentCompletedBy = '{waiterUsername}' where tableCode = {tableCode} and paymentCompletedBy is NULL and paymentRequested = 1")
    connection.commit()
    return 'success'

@app.route("/addEmployee", methods = ['POST'])
def addEmployee():
    fname = request.json['fname']
    lname = request.json['lname']
    userName = request.json['uname']
    pwd = md5(request.json['pwd'].encode()).hexdigest()
    email = request.json['email']
    userType = ["Manager", "Waiter", "Chef"].index(request.json['userType'])
    connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
    cur = connection.cursor()
    res = cur.execute("insert into remployeeaccounts (fname, lname, username, password, email, type) values ('{}','{}','{}','{}','{}',{})".format(fname, lname, userName, pwd, email, userType))
    connection.commit()
    return 'success', 201

@app.route("/delEmployee", methods = ['POST'])
def delEmployee():
    username = str(request.json['username'])
    connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
    cur = connection.cursor()
    res = cur.execute(f"delete from remployeeaccounts where username='{username}'")
    connection.commit()
    return 'success'

@app.route("/updateMenu", methods = ['POST'])
def updateMenu():
    itemID = int(request.json['itemID'])
    desc = request.json['desc']
    price = float(request.json['price'])
    avail = int(request.json['avail'])
    connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
    cur = connection.cursor()
    res = cur.execute(f"update rmenu set descr = '{desc}', price = {price}, avail = {avail}  where itemID = {itemID}")
    connection.commit()
    return 'success'

@app.route("/addMenuItem", methods = ['POST'])
def addMenuItem():
    name = request.json['name']
    desc = request.json['desc']
    itemType = request.json['itemType'][0].lower()
    price = float(request.json['price'])
    avail = 1
    connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
    cur = connection.cursor()
    res = cur.execute(f"select max(itemid) from rmenu")
    itemID = int(list(res)[0][0]) + 1

    imgurl = request.json['imgurl']
    resp = requests.get(imgurl)
    f = open("static/images/"+name+".jpg", "wb")
    f.write(resp.content)
    f.close()

    cur = connection.cursor()
    res = cur.execute(f"insert into rmenu values({itemID}, '{name}', '{desc}', {price}, '{itemType}', {avail} )")
    connection.commit()
    return 'success'

@app.route('/changePassword', methods=['POST'])
def changePassword():
    username = sessions[request.cookies['sessionID']].username
    currpass = request.get_json()['currpwd']
    hashed = md5(currpass.encode()).hexdigest()
    newpass = request.get_json()['newpwd']
    confpass = request.get_json()['confpwd']
    connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
    cur = connection.cursor()
    res = cur.execute(f"select password from remployeeaccounts where username='{username}'")
    pwd = list(res)[0][0]
    if (pwd == hashed and newpass == confpass and newpass):
        newpasshashed = md5(newpass.encode()).hexdigest()
        res = cur.execute(f"update remployeeaccounts set password ='{newpasshashed}' where username='{username}'")
        connection.commit()
        return 'success', 200
    else:
        return 'fail', 401

@app.route("/salesHistory", methods = ['POST'])
def salesHistory():
    startDate = str(request.json['startDate'])
    endDate = str(request.json['endDate'])   
    connection = cx_Oracle.connect("b00079866/b00079866@coeoracle.aus.edu:1521/orcl")
    cur = connection.cursor()
    orders = list(cur.execute(f"select ordernum from rorders where o_date between TO_DATE('{startDate}', 'dd/mm/yyyy') and TO_DATE('{endDate}', 'dd/mm/yyyy')"))
    print("Orders=" , orders)
    cur = connection.cursor()
    orderDetails = list(cur.execute("select ordernum, itemid, qty from rorderdetails"))
    print("orderDetails=" , orderDetails)
    cur = connection.cursor()
    menu = list(cur.execute("select itemid, name, price from rmenu"))
    print("menu=" , menu)
 
    sales=[]
    for item in orders:
        for details in orderDetails:
            if item[0]==details[0]:
                for menuItem in menu:
                    if details[1]==menuItem[0]:
                        sales.append((item[0],menuItem[1],details[2],details[2]*menuItem[2]))            
    '''totals = []
    for item in orders:
        total = sum([x[3] for x in sales if x[0]==item[0]])
        totals.append([item[0],total])
    totals = {}
    for item in orders:
        total = sum([x[3] for x in sales if x[0]==item[0]])
        totals[item[0]]=total'''
    sales=[]
    for item in orders:
        for details in orderDetails:
            if item[0]==details[0]:
                for menuItem in menu:
                    if details[1]==menuItem[0]:
                        dic = {'Order Number' : item[0],'Item Name' : menuItem[1], 'Quantity' : details[2], 'Total Cost' : details[2]*menuItem[2] }
                        sales.append(dic)
    

    return json.dumps(sales)