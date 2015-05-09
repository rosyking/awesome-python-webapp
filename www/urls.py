#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

__author__ = 'Henry Wang'

import re, hashlib, time
from web import get, view, ctx, post, interceptor,seeother
from apis import api, APIError, APIValueError, APIPermissionError, APIResourceNotFoundError
from models import User, Blog
from config import configs

_COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret


_RE_MD5 = re.compile(r'^[0-9a-f]{32}$')
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-_]+\@[a-z0-9\-_]+(\.[a-z0-9\-_]+){1,4}$')


@view('blogs.html')
@get('/')
def index():
    blogs = Blog.find_all()
    # user = User.find_first('where email=?', 'admin@example.com')
    user= ctx.request.user
    return dict(blogs=blogs, user=user)


@api
@get('/api/users')
def api_get_users():
    users = User.find_by('order by created_at desc')
    for user in users:
        user.password = '******'
    return dict(users=users)


@api
@post('/api/users')
def register_user():
    i = ctx.request.input(name='', email='', password='')
    name = i.name.value.strip()
    email = i.email.value.strip().lower()
    password = i.password.value
    if not name:
        raise APIValueError('name')
    if not email or not _RE_EMAIL.search(email):
        raise APIValueError('email')
    if not password or not _RE_MD5.search(password):
        raise APIValueError('password')
    user = User.find_first('where email=?', email)
    if user:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    user = User(name=name, email=email, password=password, image='http://www.gravatar.com/avatar/{}?d=mm&s=120'.
                format(hashlib.md5(email.encode('ascii')).hexdigest()))
    user.insert()
    cookie = make_signed_cookie(user.id, user.password, None)
    ctx.response.set_cookie(_COOKIE_NAME,cookie)
    return user


@view('register.html')
@get('/register')
def register():
    return dict()


@view('signin.html')
@get('/signin')
def signin():
    return dict()


def make_signed_cookie(id, password, max_age):
    # build cookie string by: id-expires-md5
    expires = str(int(time.time() + (max_age or 86400)))
    L = [id, expires, hashlib.md5('{}-{}-{}-{}'.format(id, password, expires, _COOKIE_KEY).encode('utf8')).hexdigest()]
    return '-'.join(L)

@api
@post('/api/authenticate')
def authenticate():
    i = ctx.request.input(remember='',email='',password='')
    email = i.email.value.strip().lower()
    password = i.password.value
    remember = i.remember.value
    user = User.find_first('where email=?',email)
    if user is None:
        raise APIError('auth:failed','email','Invalid email.')
    elif user.password != password:
        raise APIError('auth:failed','password','Invalid password.')
    max_age = 604800 if remember == 'true' else None
    cookie = make_signed_cookie(user.id, user.password, max_age)
    ctx.response.set_cookie(_COOKIE_NAME,cookie)
    return user


@interceptor('/')
def user_interceptor(next):
    user = None
    cookie = ctx.request.cookies.get(_COOKIE_NAME)
    if cookie:
        user=parse_signed_cookie(cookie)
    ctx.request.user = user
    return next()


def parse_signed_cookie(cookie_str):
    try:
        L=cookie_str.split('-')
        if len(L) != 3:
            return None
        id, expires, md5 = L
        if int(expires) < time.time():
            return None
        user = User.get(id)
        if user is None:
            return None
        if md5 != hashlib.md5('{}-{}-{}-{}'.format(id, user.password, expires, _COOKIE_KEY).encode('utf8')).hexdigest():
            return None
        return user
    except Exception as e:
        return None


@get('/signout')
def signout():
    ctx.response.delete_cookie(_COOKIE_NAME)
    raise seeother('/')