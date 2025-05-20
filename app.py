from flask import Flask, request, jsonify, render_template,redirect,make_response
import base64
from datetime import datetime
import qrcode
from io import BytesIO
import json

import pgapp as pg

app = Flask(__name__)

def generate_qr(username, event_id):
    try:
        # Compact data in JSON format
        data = json.dumps({"username": username, "event_id": event_id}, separators=(',', ':'))
        
        # Generate the QR Code
        qr = qrcode.QRCode(
            version=None,  # Auto-adjust version
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        # Create the QR image
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")  # Convert to RGB for JPG

        # Convert the image to base64 in JPG format
        buffer = BytesIO()
        img.save(buffer, format="JPEG")
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')

        return f"data:image/jpeg;base64,{img_base64}"
    except Exception as e:
        return f"Error generating QR code: {str(e)}"

@app.route('/img_upload', methods=['POST'])
def upload_image():
    uploaded_file = request.files['image']
    binary_data=uploaded_file.read()
    mimetype = uploaded_file.mimetype
    pg.cursor.execute("INSERT INTO images(data,mimetype) VALUES(%s,%s) RETURNING id",(binary_data,mimetype))
    pg.conn.commit()
    return {"status_code":200,"message":"Ok","id":pg.cursor.fetchone()[0]}
    
@app.route('/',methods=['GET'])
def index():
    username=request.cookies.get("username")
    secret_key=request.cookies.get("secret_key")
    pg.cursor.execute("SELECT * FROM events ORDER BY date DESC;")
    latest=pg.cursor.fetchall()[0]
    if len(latest[5])==0:
        latest=list(latest)
        latest[5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
        latest=tuple(latest)
    else:
        latest=list(latest)
        latest[5]=pg.pgGetImage(latest[5][0])
        latest=tuple(latest)
        current_datetime = datetime.now()
        formatted_datetime = str(current_datetime.strftime("%Y-%m-%d %H:%M:%S"))

    upcoming_events=[]
    pg.cursor.execute("SELECT * FROM events ORDER BY date DESC;")
    
    for event in pg.cursor.fetchall():
        if str(event[4])>=formatted_datetime:
            upcoming_events.append(event)
        else:
            break
    
    #get images
    for i in range(len(upcoming_events)):
        if (len(upcoming_events[i][5])==0):
            upcoming_events[i]=list(upcoming_events[i])
            upcoming_events[i][5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
            upcoming_events[i]=tuple(upcoming_events[i])
        else:
            upcoming_events[i]=list(upcoming_events[i])
            upcoming_events[i][5]=pg.pgGetImage(upcoming_events[i][5][0])
            upcoming_events[i]=tuple(upcoming_events[i])    
    
    if request.cookies.get("secret_key"):
        pg.cursor.execute("SELECT * FROM user_stats WHERE username=%s;",(username,))
        user=pg.cursor.fetchone()
        points=0
        if user[3]!=None:
            for i in user[3]:
                points+=i["points"]
        
                
        registered_events=[]
        if secret_key!=None:
            for event_id in pg.pgGetRecentEvents(username,secret_key):
                event = pg.pgGetEvent(event_id)
                if str(event[4])>formatted_datetime:
                    registered_events.append(event)
        #get images
        for i in range(len(registered_events)):
            if (len(registered_events[i][5])==0):
                registered_events[i]=list(registered_events[i])
                registered_events[i][5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
                registered_events[i]=tuple(registered_events[i])
            else:
                registered_events[i]=list(registered_events[i])
                registered_events[i][5]=pg.pgGetImage(registered_events[i][5][0])
                registered_events[i]=tuple(registered_events[i])
        
        for i in range(len(registered_events)):
            date = registered_events[i][4]
            time_difference=date-datetime.now()
            registered_events[i]=list(registered_events[i])
            registered_events[i][4]=time_difference.days
            registered_events[i]=tuple(registered_events[i])
        
        
        if user[1]==None:
            user=list(user)
            user[1]=[]
        return render_template('index.html',
                               username=request.cookies.get("username"),
                               profile_link='/myprofile',
                               points=points,
                               rank=pg.pgGetRank(username),
                               attended_events=len(user[1]),
                               upcoming_events=upcoming_events,
                               registered_events=registered_events,
                               latest=latest
                               )
    else:
        return render_template('index.html',
                               username="Guest User",
                               profile_link='/login',
                               latest=latest,
                               upcoming_events=upcoming_events)

@app.route('/login',methods=["GET"])
def login():
    if request.cookies.get("secret_key")!=None:
        return redirect('/')
    else:
        return render_template('login.html',username="Guest User",profile_link='/login')

@app.route('/signup',methods=["GET"])
def signup():
    if request.cookies.get("secret_key"):
        return redirect('/')
    else:
        return render_template('signup.html',username="Guest User",profile_link='/login')

@app.route('/api/login',methods=["POST"])
def apiLogin():
    resp = pg.pgLogin(request.form['username'],request.form['password'])
    if resp["status_code"]==200:
        secret_key=resp["secret_key"]
        response = make_response(redirect('/'))
        response.set_cookie('username',request.form['username'])
        response.set_cookie('secret_key',secret_key)
        return response
    else:
        return render_template('login.html',username="Guest User",profile_link='/login',message=resp['message'])

@app.route('/api/signup',methods=["POST"])
def apiSignup():
    resp = pg.pgCreateUser(request.form['username'],request.form['password'],['student'])
    return redirect('/login')

@app.route('/logout',methods=["GET"])
def logout():
    pg.pgLogout(request.cookies['username'],request.cookies['secret_key'])
    response = make_response(redirect('/login'))
    response.set_cookie('secret_key','',expires=0)
    response.set_cookie('username','',expires=0)
    return response

@app.route('/create_event',methods=['GET'])
def createEvent():
    if request.cookies.get('username')!=None:
        roles=pg.pgUserFetch(request.cookies.get('username'))["data"]["roles"]
        if "organizer" in roles or "admin" in roles:
            return render_template('createEvent.html',username=request.cookies.get("username"),profile_link='/myprofile',auth=True)
        else:
            return render_template('createEvent.html',username=request.cookies.get("username"),profile_link='/myprofile',auth=False)
        
    else:
        return redirect('/login')

@app.route('/api/create_event',methods=["POST"])
def apiCreateEvent():
    binary_data=request.files['image'].read()
    mimetype=request.files['image'].mimetype
    pg.cursor.execute("INSERT INTO images(data,mimetype) VALUES(%s,%s) RETURNING id",(binary_data,mimetype))
    pg.conn.commit()
    image_id=pg.cursor.fetchone()[0]
    if pg.pgAuthorizeCreateEvent(request.cookies.get('username'),request.cookies.get('secret_key')):
        date={
            "year":int(request.form['year']),
            "month":int(request.form['month']),
            "day":int(request.form['day']),
            "hour":int(request.form['hour']),
            "minute":int(request.form['minute']),
        }
        resp = pg.pgCreateEvent(request.cookies.get('username'),
                         request.form['eventName'],
                         request.form['description'],
                         request.form['category'],
                         date,
                         [image_id],
                         [request.cookies.get('username')]
                         )
        if resp['status_code']==200:
            return render_template('createEventConfirm.html')
        else:
            return render_template('createEvent.html',username=request.cookies.get("username"),profile_link='/myprofile',message=resp['message'])

@app.route('/myprofile',methods=["GET"])
def myprofile():
    username=request.cookies.get('username')
    secret_key=request.cookies.get('secret_key')
    if username==None:
        return redirect('/login')
    pg.cursor.execute("SELECT * FROM user_stats WHERE username=%s;",(username,))
    user=pg.cursor.fetchone()
    points=0
    if user[3]!=None:
        for i in user[3]:
            points+=i["points"]
    recent_events_ids=pg.pgGetRecentEvents(username,secret_key)
    if recent_events_ids==False:
        return redirect('/login')
    recent_events=[]
    for id in recent_events_ids:
        recent_events.append(pg.pgGetEvent(id))
        
    #get image
    for i in range(len(recent_events)):
        if (len(recent_events[i][5])==0):
            recent_events[i]=list(recent_events[i])
            recent_events[i][5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
            recent_events[i]=tuple(recent_events[i])
        else:
            recent_events[i]=list(recent_events[i])
            recent_events[i][5]=pg.pgGetImage(recent_events[i][5][0])
            recent_events[i]=tuple(recent_events[i])
    if user[1]==None:
        user=list(user)
        user[1]=[]
    return render_template('/myprofile.html',
                           username=username,
                           uprofile_rl='/myprofile',
                           workshop_count=len(user[1]),
                           points=points,rank=pg.pgGetRank(username),
                           recent_events=recent_events)
@app.route('/leaderboard',methods=["GET"])
def leaderboard():
    username = request.cookies.get('username')
    secret_key= request.cookies.get('secret_key')
    if username==None:
        return redirect('/login')
    LB=pg.pgRanklist()
    for i in range(len(LB)):
        LB[i]=list(LB[i])
        LB[i][3]=pg.pgGetPoints(LB[i][0])
    return render_template('/leaderboard.html',
                           username=username,uprofile_rl='/myprofile',
                           myrank=pg.pgGetRank(username),
                           mypoints=pg.pgGetPoints(username), 
                           myworkshops=len(pg.pgGetRecentEvents(username,secret_key)),
                           LB=LB)

@app.route('/events',methods=["GET"])
def events():
    category = request.args.get('category')
    if category==None:
        category=''
    username=request.cookies.get('username')
    if username==None:
        username="Guest User"
    pg.cursor.execute("SELECT * FROM events;")
    current_datetime = datetime.now()
    formatted_datetime = str(current_datetime.strftime("%Y-%m-%d %H:%M:%S"))
    events=pg.cursor.fetchall()
    upcoming_events=[]
    for event in events:
        if str(event[4])>formatted_datetime and category in event[3].lower():
            upcoming_events.append(event)
    upcoming_events=sorted(upcoming_events,key=lambda i:i[4],reverse=True)
    for i in range(len(upcoming_events)):
        if (len(upcoming_events[i][5])==0):
            upcoming_events[i]=list(upcoming_events[i])
            upcoming_events[i][5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
            upcoming_events[i]=tuple(upcoming_events[i])
        else:
            upcoming_events[i]=list(upcoming_events[i])
            upcoming_events[i][5]=pg.pgGetImage(upcoming_events[i][5][0])
            upcoming_events[i]=tuple(upcoming_events[i])
    return render_template('events.html',
                           username=username,
                           profile_link="/myprofile" if username!="Guest User" else "/login",
                           upcoming_events=upcoming_events,
                           selected_category=category.lower() if category!='' else 'all')

@app.route('/myevents',methods=["GET"])
def myevents():
    username=request.cookies.get('username')
    secret_key=request.cookies.get('secret_key')
    if username==None:
        username="Guest User"
    my_events=[]
    if secret_key!=None:
        for event_id in pg.pgGetCreatedEvents(username,secret_key):
            event = pg.pgGetEvent(event_id)
            my_events.append(event)
    for i in range(len(my_events)):
        if (len(my_events[i][5])==0):
            my_events[i]=list(my_events[i])
            my_events[i][5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
            my_events[i]=tuple(my_events[i])
        else:
            my_events[i]=list(my_events[i])
            my_events[i][5]=pg.pgGetImage(my_events[i][5][0])
            my_events[i]=tuple(my_events[i])
    return render_template('myEvents.html',
                           username=username,
                           profile_link="/myprofile" if username!="Guest User" else "/login",
                           my_events=my_events)

@app.route('/workshops',methods=["GET"])
def workshops():
    username=request.cookies.get('username')
    if username==None:
        username="Guest User"
    pg.cursor.execute("SELECT * FROM events;")
    current_datetime = datetime.now()
    formatted_datetime = str(current_datetime.strftime("%Y-%m-%d %H:%M:%S"))
    events=pg.cursor.fetchall()
    upcoming_events=[]
    for event in events:
        if str(event[4])>formatted_datetime:
            upcoming_events.append(event)
    upcoming_events=sorted(upcoming_events,key=lambda i:i[4])
    for i in range(len(upcoming_events)):
        if (len(upcoming_events[i][5])==0):
            upcoming_events[i]=list(upcoming_events[i])
            upcoming_events[i][5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
            upcoming_events[i]=tuple(upcoming_events[i])
        else:
            upcoming_events[i]=list(upcoming_events[i])
            upcoming_events[i][5]=pg.pgGetImage(upcoming_events[i][5][0])
            upcoming_events[i]=tuple(upcoming_events[i])
    
    return render_template('workshops.html',
                           username=username,
                           profile_link="/myprofile" if username!="Guest User" else "/login",
                           upcoming_events=upcoming_events)

@app.route('/about',methods=["GET"])
def about():
    return render_template('about.html')

@app.route('/community',methods=["GET"])
def community():
    username=request.cookies.get('username')
    if username==None:
        return redirect('/login')
    return render_template('community.html',username=username,profile_link='/myprofile',blogs=pg.pgGetBlogs())

@app.route('/api/post_blog',methods=["POST"])
def post_blog():
    username=request.cookies.get('username')
    secret_key=request.cookies.get('secret_key')
    if username==None:
        return redirect('/community')
    pg.pgPostBlog(username,secret_key,request.form['blog'],datetime.now())
    return redirect('/community')
    
@app.route('/event/<int:id>',methods=["GET"])
def event(id):
    username=request.cookies.get('username')
    secret_key=request.cookies.get('secret_key')
    if username==None:
        return redirect('/login')
    event=pg.pgGetEvent(id)     #(id,title,description,category,date,imageids,organizers,access,registered_users)
    
    #get image
    if (len(event[5])==0):
        event=list(event)
        event[5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
        event=tuple(event)
    else:
        event=list(event)
        event[5]=pg.pgGetImage(event[5][0])
        event=tuple(event)
    
    return render_template('eventDetails.html',
                    username=(username  or "Guest User"),
                    profile_link="/myprofile" if username=="Guest User" else "/login",
                    event=event
                    )
    
@app.route('/register/<int:id>',methods=["GET"])
def register(id):
    username=request.cookies.get('username')
    secret_key=request.cookies.get('secret_key')
    if username==None:
        return redirect('/login')
    event=pg.pgGetEvent(id)     #(id,title,description,category,date,imageids,organizers,access,registered_users)
    resp = pg.pgRegisterEvent(username,secret_key,id)
    alreadyRegistered=False if resp['status_code']==200 else True
    #get image
    if (len(event[5])==0):
        event=list(event)
        event[5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
        event=tuple(event)
    else:
        event=list(event)
        event[5]=pg.pgGetImage(event[5][0])
        event=tuple(event)
    
    return render_template('register.html',
                    username=username,
                    profile_link="/myprofile" if username!="Guest User" else "/login",
                    event=event,
                    alreadyRegistered=alreadyRegistered,
                    qr=generate_qr(username,id)
                    )

@app.route('/api/award',methods=["POST"])
def apiAward():
    username=request.cookies.get('username')
    secret_key=request.cookies.get('secret_key')
    if username==None:
        return redirect('/login')
    resp = pg.pgAwardPoints(username,secret_key,request.form['student-name'],request.form['event-id'],request.form['points'])
    return redirect('/award/'+str(request.form['event-id']))

@app.route('/award/<int:id>',methods=["GET"])
def award(id):
    username=request.cookies.get('username')
    secret_key=request.cookies.get('secret_key')
    registered_users=list(pg.pgGetEvent(id)[-1])
    event=pg.pgGetEvent(id)
    for i in range(len(registered_users)):
        registered_users[i]=pg.pgUserFetch(registered_users[i])
    return render_template('award.html',
                           username=username,
                           profile_link='myprofile',
                           registered_users=registered_users,
                           event_id=id,
                           event=event
                           )

@app.route('/test',methods=["GET"])
def test():
    return render_template('award.html')
if __name__ == "__main__":
    app.run(debug=True)