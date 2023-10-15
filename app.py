from flask import Flask, render_template, request, redirect, url_for, session, g
import pyrebase, json, uuid, fuzzywuzzy, datetime
from fuzzywuzzy import fuzz
import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore, storage


app = Flask(__name__)
app.debug = True
f = open('json/secret_key.txt', 'r')
app.secret_key = f.read()
f.close()
cred = credentials.Certificate('json/admin-config.json')
if not firebase_admin._apps:
    firebase = firebase_admin.initialize_app(cred,json.load(open('json/config.json')))
    firebase = pyrebase.initialize_app(json.load(open('json/config.json')))
db = firestore.client()
bucket = storage.bucket()


@app.route("/", methods = ["GET"])
def home_page():
    g.active_menu_item = 'search'
    return render_template("home_page.html", name = session['name'])

@app.before_request
def before_request():
    if 'email' not in session and request.endpoint != 'login':
        session['name'] = None
        session['email'] = None
        session['hall'] = None
        session['phone'] = None
        session['roll'] = None
        return redirect('/')

def fetch_contact(db, email):
    users = db.collection('users').get()
    for user in users:
        user = user.to_dict()
        if user['email'] == email:
            return user['name'], user['phone']


@app.route("/login", methods=["GET"])
def login():
    
    if not session['name'] == None:
        return redirect('/')
    return render_template('login.html')


@app.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    if request.method == "GET":
        return render_template('signup.html')
    email = request.form.get('email')
    password = request.form.get('password')
    name = request.form.get('name')
    roll = request.form.get('rollno')
    phone = request.form.get('phone')
    hall = request.form.get('hall')
    user = firebase.auth().create_user_with_email_and_password(email, password)
    data = {
        "name": name,
        "roll": roll,
        "phone": phone,
        "hall": hall,
        "email": email,
    }
    print(user)
    db.collection("users").add(data)
    return redirect('/login')


@app.route("/auth", methods=["POST"])
def auth():
    email = request.form.get('email')
    password = request.form.get('password')

    try:
        user = firebase.auth().sign_in_with_email_and_password(email, password)
    except:
        return render_template('login.html', error="Invalid credentials")

    doc = db.collection('users').where('email', '==', email).get()[0].to_dict()
    print(doc)
    session['email'] = doc['email']
    session['name'] = doc['name']
    session['hall'] = doc['hall']
    session['phone'] = doc['phone']
    session['roll'] = doc['roll']

    return redirect('/')





@app.route("/upload", methods=["GET"])
def upload():
    g.active_menu_item = 'upload'
    if session['email'] == None:
        return redirect('/login')
    return render_template("bookupload.html", name = session['name'])

@app.route("/upload_data", methods = ["POST"])
def upload_data():
    title = request.form.get('title')
    author = request.form.get('author')
    email = session['email']
    imagefile = request.files['imagefile']
    filename = str(uuid.uuid4())+'.jpg'
    blob = bucket.blob(filename)
    blob.upload_from_file(imagefile,content_type="image/jpeg")
    data = {'email':email, 'title': title, 'author': author, 'filename': filename, 'timestamp': datetime.datetime.now()}
    db.collection('uploads').add(data)
    return render_template("home_page.html", name = session['name'])


@app.route("/search", methods=["POST"])
def search():
    g.active_menu_item = 'search'
    keyphrase = request.form.get("keyphrase")
    print(keyphrase)
    books = db.collection('uploads').get()
    search_results = []
    imageurl = []
    myuploads = []
    for book in books:

        book = book.to_dict()
        author = book['author']
        title = book['title']
        
        print(author, title)
        if fuzz.ratio(author, keyphrase) > 50 or fuzz.ratio(title, keyphrase) > 50:
            book['allow_borrow'] = True
            if book['email'] == session['email']:
                book['allow_borrow'] = False
            
            search_results.append(book)
            blob = bucket.blob(book['filename'])
            imageurl.append(blob.generate_signed_url(datetime.timedelta(seconds=300), method='GET'))
            print(imageurl[-1])

        A = author.split(' ')
        B = title.split(' ')
        A = A+B
        for a in A:
            if fuzz.ratio(a, keyphrase) > 50 and book not in search_results:
                book['allow_borrow'] = True
                if book['email'] == session['email']:
                    book['allow_borrow'] = False
                search_results.append(book)
                blob = bucket.blob(book['filename'])
                imageurl.append(blob.generate_signed_url(datetime.timedelta(seconds=300), method='GET'))
                
    return render_template("search_results.html", search_results = search_results, imageurl = imageurl, name = session['name'])




@app.route("/request_book", methods=["POST"])
def request_book():
    req = {}
    title = request.form.get('title')
    author = request.form.get('author')
    email = request.form.get('email')
    filename = request.form.get('filename')
    trans = db.collection('transactions').where('borrower', '==', session['email']).where('filename', '==', filename).where('status', '==', 'requested').get()
    trans += db.collection('transactions').where('borrower', '==', session['email']).where('filename', '==', filename).where('status', '==', 'accepted').get()
    req['borrower'] = session['email']
    req['owner'] = email
    req['title'] = title
    req['author'] = author
    req['filename'] = filename
    req['status'] = 'requested'
    req['timestamp'] = datetime.datetime.now()
    req['transactionID'] = str(uuid.uuid4())
    
    blob = bucket.blob(filename)
    imgurl = blob.generate_signed_url(datetime.timedelta(seconds=300), method='GET')
    if len(trans) > 0:
        return render_template("already_requested.html", imgurl = imgurl, author = author, title=title, name = session['name'])
    db.collection('transactions').add(req)
    return render_template("request_confirm.html", author = author, title=title, imgurl = imgurl, name = session['name'])


@app.route("/my_uploads", methods=["GET"])
def my_uploads():
    g.active_menu_item = 'my_uploads'
    if session['email'] == None:
        return redirect('/login')
    results = []
    imageurl = []
    books = db.collection('uploads').get()
    for book in books:
        book = book.to_dict()
        if book['email'] == session['email']:
            results.append(book)
            blob = bucket.blob(book['filename'])
            imageurl.append(blob.generate_signed_url(datetime.timedelta(seconds=300), method='GET'))
    
    
    return render_template("my_uploads.html", search_results=results, imageurl = imageurl, name = session['name'])



def fetch_contact(db, email):
    user = db.collection('users').where('email', '==', email).get()[0].to_dict()
    return (user['name'], user['phone'])


def getbook(db, transactionID):
    result = db.collection('transactions').where('transactionID', '==', transactionID).get()[0].to_dict()
    book = db.collection('uploads').where('filename', '==', result['filename']).get()[0]
    return book

@app.route("/updates", methods=["GET"])
def updates():
    g.active_menu_item = 'updates'
    if session['email'] == None:
        return redirect('/login')
    
    transactions = db.collection('transactions').get()
    updates = []
    #{'title', 'name', 'email','owner', 'borrower', 'phone', 'type', 'timestamp', 'transactionID'}
    for t in transactions:
        t = t.to_dict()
        update = {}
        if t['borrower'] == session['email'] and t['status'] == 'accepted':
            update['title'] = t['title']
            update['email'] = t['owner']
            name, phone = fetch_contact(db, update['email'])
            update['owner'] = name
            update['borrower'], _ = fetch_contact(db, t['borrower'])
            update['phone'] = phone
            update['type'] = 1
            update['timestamp'] = t['timestamp']
            update['transactionID'] = t['transactionID']
            updates.append(update)
            
        
        if t['owner'] == session['email'] and t['status'] == 'requested':
            update['title'] = t['title']
            update['email'] = t['owner']
            name, phone = fetch_contact(db, update['email'])
            update['owner'] = name
            update['borrower'], _ = fetch_contact(db, t['borrower'])
            update['phone'] = phone
            book = getbook(db, t['transactionID'])
            if book.to_dict()['availability']:
                update['type'] = 2
            else:
                update['type'] = 8
            update['timestamp'] = t['timestamp']
            update['transactionID'] = t['transactionID']
            updates.append(update)

        if t['owner'] == session['email'] and t['status'] == 'accepted':
            update['title'] = t['title']
            update['email'] = t['owner']
            name, phone = fetch_contact(db, update['email'])
            update['owner'] = name
            update['borrower'], _ = fetch_contact(db, t['borrower'])
            update['phone'] = phone
            update['type'] = 3
            update['timestamp'] = t['timestamp']
            update['transactionID'] = t['transactionID']
            updates.append(update)

        
        if t['borrower'] == session['email'] and t['status'] == 'declined':
            update['title'] = t['title']
            update['email'] = t['owner']
            name, phone = fetch_contact(db, update['email'])
            update['owner'] = name
            update['borrower'], _ = fetch_contact(db, t['borrower'])
            update['phone'] = phone
            update['type'] = 4
            update['timestamp'] = t['timestamp']
            update['transactionID'] = t['transactionID']
            updates.append(update)
        
        if t['owner'] == session['email'] and t['status'] == 'returned':
            update['title'] = t['title']
            update['email'] = t['owner']
            name, phone = fetch_contact(db, update['email'])
            update['owner'] = name
            update['borrower'], _ = fetch_contact(db, t['borrower'])
            update['phone'] = phone
            update['type'] = 5
            update['timestamp'] = t['timestamp']
            update['transactionID'] = t['transactionID']
            updates.append(update)
        
        if t['borrower'] == session['email'] and t['status'] == 'returned':
            update['title'] = t['title']
            update['email'] = t['owner']
            name, phone = fetch_contact(db, update['email'])
            update['owner'] = name
            update['borrower'], _ = fetch_contact(db, t['borrower'])
            update['phone'] = phone
            update['type'] = 6
            update['timestamp'] = t['timestamp']
            update['transactionID'] = t['transactionID']
            updates.append(update)

        if t['borrower'] == session['email'] and t['status'] == 'requested':
            update['title'] = t['title']
            update['email'] = t['owner']
            name, phone = fetch_contact(db, update['email'])
            update['owner'] = name
            update['borrower'], _ = fetch_contact(db, t['borrower'])
            update['phone'] = phone
            update['type'] = 7
            update['timestamp'] = t['timestamp']
            update['transactionID'] = t['transactionID']
            updates.append(update)
        


    updates = sorted(updates, key = lambda updates: updates['timestamp'], reverse=True)
    print(updates)
    return render_template("updates.html", updates = updates, name = session['name'])


@app.route('/accept', methods = ["POST"])
def accept():
    transactionID = request.form.get('transactionID')
    transaction = db.collection('transactions').where('transactionID', '==', transactionID).get()[0]
    db.collection('transactions').document(transaction.id).update({'timestamp': datetime.datetime.now()})
    db.collection('transactions').document(transaction.id).update({'status': 'accepted'})
    transaction = transaction.to_dict()
    book = db.collection('uploads').where('filename', '==', transaction['filename']).get()[0]
    db.collection('uploads').document(book.id).update({'availability': False})
    
    blob = bucket.blob(transaction['filename'])
    imageurl = blob.generate_signed_url(datetime.timedelta(seconds=300), method='GET')
    borrower, _ = fetch_contact(db, transaction['borrower'])
    print(borrower)
    return render_template('accepted.html', transaction = transaction, imageurl=imageurl, name = session['name'])

@app.route('/decline', methods = ["POST"])
def decline():
    transactionID = request.form.get('transactionID')
    transaction = db.collection('transactions').where('transactionID', '==', transactionID).get()[0]
    db.collection('transactions').document(transaction.id).update({'timestamp': datetime.datetime.now()})
    db.collection('transactions').document(transaction.id).update({'status': 'declined'})
    blob = bucket.blob(transaction.to_dict()['filename'])
    imageurl = blob.generate_signed_url(datetime.timedelta(seconds=300), method='GET')
    borrower, _ = fetch_contact(db, transaction.to_dict()['borrower'])
    print(borrower)
    return render_template('declined.html', transaction = transaction.to_dict(), imageurl=imageurl, borrower=borrower, name = session['name'])


@app.route('/myprofile', methods = ["GET"])
def myprofile():
    g.active_menu_item = 'myprofile'
    if session['email'] == None:
        return redirect('/login')
    return render_template("profile.html", session = session, name = session['name'])


@app.route('/logout', methods = ["POST"])
def logout():
    session['name'] = None
    session['email'] = None
    session['hall'] = None
    session['phone'] = None
    return redirect('/')


@app.route('/borrowed', methods = ["GET"])
def borrowed():
    g.active_menu_item = 'borrowed'
    if session['email'] == None:
        return redirect('/login')
    
    search_results = []
    imageurls = []
    results = db.collection('transactions').where('borrower', '==', session['email']).where('status', '==', 'accepted').get()
    results += db.collection('transactions').where('borrower', '==', session['email']).where('status', '==', 'returned').get()
    for result in results:
        result = result.to_dict()
        blob = bucket.blob(result['filename'])
        imageurl = blob.generate_signed_url(datetime.timedelta(seconds=300), method='GET')
        result['imageurl'] = imageurl
        result['owner_name'], result['phone'] = fetch_contact(db,result['owner'])
        search_results.append(result)
    search_results = sorted(search_results, key = lambda search_results: search_results['timestamp'], reverse=True)

    return render_template("borrowed.html", search_results = search_results, name = session['name'])



@app.route('/lended', methods=["GET"])
def lended():
    g.active_menu_item = 'lended'
    if session['email'] == None:
        return redirect('/login')
    
    search_results = []
    imageurls = []
    results = db.collection('transactions').where('owner', '==', session['email']).where('status', '==', 'accepted').get()
    results += db.collection('transactions').where('owner', '==', session['email']).where('status', '==', 'returned').get()
    for result in results:
        result = result.to_dict()
        blob = bucket.blob(result['filename'])
        imageurl = blob.generate_signed_url(datetime.timedelta(seconds=300), method='GET')
        result['imageurl'] = imageurl
        result['borrower_name'], result['phone'] = fetch_contact(db,result['borrower'])
        search_results.append(result)
    sorted(search_results, key = lambda search_results: search_results['timestamp'], reverse=True)

    return render_template("lended.html", search_results = search_results, name = session['name'])

    
@app.route('/returned', methods = ["POST"])
def returned():
    transactionID = request.form.get('transactionID')
    result = db.collection('transactions').where('transactionID', '==', transactionID).get()[0]
    db.collection('transactions').document(result.id).update({'status': 'returned'})
    db.collection('transactions').document(result.id).update({'timestamp': datetime.datetime.now()})
    result = result.to_dict()
    result['status'] = 'returned'
    result['timestamp'] = datetime.datetime.now()

    book = getbook(db, transactionID)
    db.collection('uploads').document(book.id).update({'availability':True})
    result['borrower_name'], _ = fetch_contact(db, result['borrower'])
    blob = bucket.blob(result['filename'])
    imageurl = blob.generate_signed_url(datetime.timedelta(seconds=300), method='GET')
    return render_template("returned.html", result = result, imageurl = imageurl)

@app.route('/takeback', methods=["POST"])
def takeback():
    transactionID = request.form.get('transactionID')
    result = db.collection('transactions').where('transactionID', '==', transactionID).get()[0]
    db.collection('transactions').document(result.id).delete()
    result = result.to_dict()
    blob = bucket.blob(result['filename'])
    imageurl = blob.generate_signed_url(datetime.timedelta(seconds=300), method='GET')
    return render_template("takeback.html", result = result, imageurl = imageurl)
    
