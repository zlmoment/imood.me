#!/usr/bin/env python
# -*- coding: utf-8 -*-
from flask import Flask, request, session, g, redirect, url_for, render_template, flash, make_response
from random import choice
import mysql.connector
import hashlib
import datetime
import pytz
from decorators import require_login
import os
PROJDIR = os.path.abspath(os.path.dirname(__file__))

# configuration
SITE_TITLE = u'小时光'
SITE_DESC = u'小时光'
DEBUG = True
SECRET_KEY = 'development key'
UPLOAD_FOLDER = PROJDIR+'/static/img/avatar'
ALLOWED_EXTENSIONS = set(['png', 'jpg'])

app = Flask(__name__)
app.config.from_object(__name__)

def connect_db():
    try:
        conn = mysql.connector.connect(user='root', password='', host='localhost', database='imood', charset="utf8")
    except Exception, e:
        #print "Failed connection!", e
        return
    return conn

@app.before_request
def before_request():
    g.db = connect_db()
    g.cursor = g.db.cursor()
    g.user = getCurrentUser()

@app.teardown_request
def teardown_request(exception):
    g.db.commit()
    g.cursor.close()
    g.db.close()

@app.route('/')
def index():
    if g.user:
        g.cursor.execute("""select * from imood_posts where username='%s';""" % g.user['username'])
        result = g.cursor.fetchall()
        blogs = []
        for r in result:
            temp = {}
            temp['url'] = r[0]
            temp['time'] = r[2]
            temp['summary'] = r[3][0:100]+" ..."
            blogs.append(temp)
        return render_template('index2.html',blogs = blogs)
    username = request.cookies.get('username')
    password = request.cookies.get('password')
    if checklogin(username,password):
        session['logged_in'] = True
        session['username'] = username
        g.cursor.execute("""select * from imood_posts where username='%s';""" % username)
        result = g.cursor.fetchall()
        blogs = []
        for r in result:
            temp = {}
            temp['url'] = r[0]
            temp['time'] = r[2]
            temp['summary'] = r[3][0:50]
            blogs.append(temp)
        return render_template('index2.html',blogs = blogs)
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    user = {}
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        repassword = request.form['repassword']
        email = request.form['email']
        checkbox = False
        if 'agreeornot' in request.form:
            checkbox = request.form['agreeornot']
        privacy = int(request.form['privacy'])
        user = dict(username = username, password = password, repassword = repassword, email = email, agreeornot = checkbox, privacy = privacy)
        if username == "" or password == "" or repassword == "" or email == "":
            flash(u'请填写完整')
        elif checkbox == False:
            flash(u'您必须同意协议才能注册。')
        elif password != repassword:
            flash(u'两次密码输入不一致。')
        else:
            #check if username has already existed
            g.cursor.execute("""select username from imood_users where username='%s';""" % user['username'])
            result = g.cursor.fetchall()
            if result != []:
                flash(u'用户名已存在，请重新尝试。')
                return render_template('register.html', user = user)
            #check if email has already existed
            g.cursor.execute("""select email from imood_users where username='%s';""" % user['email'])
            result = g.cursor.fetchall()
            if result != []:
                flash(u'此邮箱已存在，请重新尝试。')
                return render_template('register.html', user = user)
            url = create_token()
            #check if url has already existed
            g.cursor.execute("""select url from imood_users where url='%s';""" % url)
            result = g.cursor.fetchall()
            if result != []:
                url = create_token()
            #all is well
            user['password'] = md5encrypt(user['password'])
            sql = """insert into `imood_users` (`username`,`password`,`regtime`,`email`,`url`,`private`) values ('%s','%s','%s','%s','%s',%d);"""\
                        % (user['username'],user['password'],getCurrentTime(),user['email'],url,user['privacy'])
            g.cursor.execute(sql)
            #insert first diary
            sql = """insert into `imood_posts` (`username`,`pubtime`,`content`) values ('%s','%s','%s');"""\
                        % (user['username'],getCurrentTime(),u"今天注册了小时光，开始记录自己的心情。")
            g.cursor.execute(sql)
            session['logged_in'] = True
            session['username'] = username
            g.user = user
            return redirect(url_for('index'))
    return render_template('register.html', user = user)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    remember = "no"
    if 'remember' in request.form:
        remember = request.form['remember']
    if username == "" or password == "":
        flash(u'请填写用户名和密码')
        return redirect(url_for('index'))
    password = md5encrypt(password)
    result = checklogin(username,password)
    if result == False:
        flash(u'用户名或密码错误')
    else:
        session['logged_in'] = True
        session['username'] = username
        g.user = getCurrentUser()
        #print g.user
        if remember == "remember-me":
            resp = make_response(redirect('/'+g.user['url']))
            resp.set_cookie('username', username, max_age = 1209000)
            resp.set_cookie('password', password, max_age = 1209000)
            return resp
        return redirect('/'+g.user['url'])
    return redirect(url_for('index'))

def checklogin(username,password):
    g.cursor.execute("""select username,password from imood_users where username='%s';""" % username)
    result = g.cursor.fetchall()
    if result == []:
        return False
    elif username == result[0][0] and password == result[0][1]:
        return True
    else:
        return False

def getCurrentUser():
    if 'logged_in' not in session or 'username' not in session:
        return None
    g.cursor.execute("""select * from imood_users where username='%s';""" % session['username'])
    result = g.cursor.fetchall()
    colums = ('id', 'username', 'password', 'regtime', 'gender', 'avatar', 'email', 'url', 'nickname', 'solo', 'private')
    result = dict(zip(colums,result[0]))
    return result

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash(u"您已经成功登出小时光。")
    resp = make_response(redirect(url_for('index')))
    resp.set_cookie('username', None, max_age = 0)
    resp.set_cookie('password', None, max_age = 0)
    return resp

@app.route('/diary/add', methods=['GET','POST'])
@require_login
def diaryadd():
    nowtime = getCurrentTime()
    if request.method == 'POST':
        content = request.form['content']
        if content == "":
            flash(u"时光荏苒，不想说些什么吗？")
            return render_template('diaryadd.html')
        #content = content.replace("\n","<br />")
        content = content.replace("\r\n","\n")
        sql = """insert into `imood_posts` (`username`,`pubtime`,`content`) values ('%s','%s','%s');"""\
                        % (g.user['username'],nowtime,content)
        g.cursor.execute(sql)
        return redirect("/"+g.user['username'])
    return render_template('diaryadd.html',nowtime = nowtime)

@app.route('/account', methods=['GET','POST'])
@require_login
def account():
    return render_template('account.html')

# avatar upload
@app.route('/account/upload', methods=['POST'])
@require_login
def avatar_upload():
    afile = request.files['upload_file']
    if afile and allowed_file(afile.filename):
        filename = g.user['username']+'.'+afile.filename.rsplit('.', 1)[1].lower()
        afile.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        sql = ("""update `imood_users` set `avatar`='%s' where `username`='%s';"""\
            % (filename,g.user['username']))
        g.cursor.execute(sql)  
        flash(u"保存成功,请刷新页面查看新头像！")
    return redirect("/account")
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
           
@app.route('/account/personal', methods=['POST'])
@require_login
def personal_update():
    username = g.user['username']
    nickname = request.form['nickname']
    solo = request.form['solo']
    email = request.form['email']
    sql = ("""update `imood_users` set `nickname`='%s', `solo`='%s', `email`='%s' where `username`='%s';"""\
            % (nickname,solo,email,username))
    g.cursor.execute(sql)        
    flash(u"保存成功")
    return redirect("/account")

@app.route('/account/privacy', methods=['POST'])
@require_login
def privacy_update():
    privacy = int(request.form['privacy'])
    sql = ("""update `imood_users` set `private`=%d where `username`='%s';"""\
            % (privacy,g.user['username']))
    g.cursor.execute(sql)        
    flash(u"保存成功")
    return redirect("/account")

@app.route('/<url>', methods=['GET','POST'])
@require_login
def myhome(url):
    sql = """select * from `imood_posts` where `username`='%s' order by `id` desc limit 1;"""\
                    % (g.user['username'])
    g.cursor.execute(sql)
    result = g.cursor.fetchall()
    if result[0] == ():
        result = None
    else:
        colums = ('id', 'username', 'pubtime', 'content')
        result = dict(zip(colums,result[0]))
        result['content'] = result['content'].split("\n")
    return render_template('myhome.html',result=result)

@app.route('/diary/<url>', methods=['GET'])
def showdiary(url):
    # check if user has permission
    
    sql = """select * from `imood_posts` where `id`=%s;"""\
                    % (url)
    g.cursor.execute(sql)
    result = g.cursor.fetchall()
    if result[0] == ():
        result = None
    else:
        colums = ('id', 'username', 'pubtime', 'content')
        result = dict(zip(colums,result[0]))
        result['content'] = result['content'].split("\n")
    if g.user:
        if result['username'] == g.user['username']:
            return render_template('showdiary.html',result=result)
        elif g.user.private == '1':#open to all
            return render_template('showdiary.html',result=result)
        else:
            return render_template('showdiary.html',result=None)
    else:
        sql = """select private from `imood_users` where `username`='%s';"""\
                    % (result['username'])
        g.cursor.execute(sql)
        result2 = g.cursor.fetchall()
        if result2[0][0] == 1:
            return render_template('showdiary.html',result=result)
        else:
            return render_template('showdiary.html',result=None)
    return render_template('showdiary.html',result=result)

def md5encrypt(psw):
    m = hashlib.md5()
    m.update(psw)
    return m.hexdigest().upper()

def create_token(length=6):
    chars = ('123456789')
    salt = ''.join([choice(chars) for i in range(length)])
    return salt

def getCurrentTime():
    tz = pytz.timezone('Asia/Chongqing')
    t = datetime.datetime.now(tz)
    return str(t.year)+"-"+str(t.month)+"-"+str(t.day)+" "+str(t.hour)+":"+str(t.minute)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
