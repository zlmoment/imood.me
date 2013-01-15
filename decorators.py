#encoding:utf-8

from flask import g
from flask import url_for, redirect, flash
import functools

class require_role(object):
    def __init__(self, role):
        self.role = role

    def __call__(self, method):
        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            if not g.user:
                url = url_for('index')
                flash(u"此操作需要登陆。")
                return redirect(url)
            else:
                return method(*args, **kwargs)
        return wrapper

require_login = require_role(None)
