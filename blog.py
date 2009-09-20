#!/usr/bin/env python
#
# Copyright 2009 Bret Taylor
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import functools
import markdown
import os
import os.path
import re
import tornado.web
import tornado.wsgi
import unicodedata
import wsgiref.handlers

from google.appengine.api import users
from google.appengine.ext import db


class Entry(db.Model):
    """A single blog entry."""
    author = db.UserProperty()
    title = db.StringProperty(required=True)
    slug = db.StringProperty(required=True)
    body = db.TextProperty(required=True)
    markdown = db.TextProperty(required=True)
    published = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)


def administrator(method):
    """Decorate with this method to restrict to site admins."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.current_user:
            if self.request.method == "GET":
                self.redirect(self.get_login_url())
                return
            raise web.HTTPError(403)
        elif not self.current_user.administrator:
            if self.request.method == "GET":
                self.redirect("/")
                return
            raise web.HTTPError(403)
        else:
            return method(self, *args, **kwargs)
    return wrapper


class BaseHandler(tornado.web.RequestHandler):
    """Implements Google Accounts authentication methods."""
    def get_current_user(self):
        user = users.get_current_user()
        if user: user.administrator = users.is_current_user_admin()
        return user

    def get_login_url(self):
        return users.create_login_url(self.request.uri)

    def render_string(self, template_name, **kwargs):
        # Let the templates access the users module to generate login URLs
        return tornado.web.RequestHandler.render_string(
            self, template_name, users=users, **kwargs)


class HomeHandler(BaseHandler):
    def get(self):
        entries = db.Query(Entry).order('-published').fetch(limit=3)
        if not entries:
            if not self.current_user or self.current_user.administrator:
                self.redirect("/compose")
                return
        self.render("home.html", entries=entries)


class EntryHandler(BaseHandler):
    @tornado.web.removeslash
    def get(self, slug):
        entry = db.Query(Entry).filter("slug =", slug).get()
        if not entry: raise tornado.web.HTTPError(404)
        self.render("entry.html", entry=entry)


class ArchiveHandler(BaseHandler):
    def get(self):
        entries = db.Query(Entry).order('-published')
        self.render("archive.html", entries=entries)


class AboutHandler(BaseHandler):
    def get(self):
        self.render("about.html")


class FeedHandler(BaseHandler):
    def get(self):
        entries = db.Query(Entry).order('-published').fetch(limit=10)
        self.set_header("Content-Type", "application/atom+xml")
        self.render("feed.xml", entries=entries)


class ComposeHandler(BaseHandler):
    @administrator
    def get(self):
        key = self.get_argument("key", None)
        entry = Entry.get(key) if key else None
        self.render("compose.html", entry=entry)

    @administrator
    def post(self):
        key = self.get_argument("key", None)
        if key:
            entry = Entry.get(key)
            entry.title = self.get_argument("title")
            entry.body = self.get_argument("markdown")
            entry.markdown = markdown.markdown(self.get_argument("markdown"))
        else:
            title = self.get_argument("title")
            slug = unicodedata.normalize("NFKD", title).encode(
                "ascii", "ignore")
            slug = re.sub(r"[^\w]+", " ", slug)
            slug = "-".join(slug.lower().strip().split())
            if not slug: slug = "entry"
            while True:
                existing = db.Query(Entry).filter("slug =", slug).get()
                if not existing or str(existing.key()) == key:
                    break
                slug += "-2"
            entry = Entry(
                author=self.current_user,
                title=title,
                slug=slug,
                body=self.get_argument("markdown"),
                markdown=markdown.markdown(self.get_argument("markdown")),
            )
        entry.put()
        self.redirect("/entry/" + entry.slug)


class EntryModule(tornado.web.UIModule):
    def render(self, entry, show_comments=False):
        if show_comments:
            self.show_comments = True
        else:
            self.show_count = True
        return self.render_string("modules/entry.html", entry=entry,
                                  show_comments=show_comments)

    def embedded_javascript(self):
        if getattr(self, "show_count", False):
            return self.render_string("disquscount.js")
        return None

    def javascript_files(self):
        if getattr(self, "show_comments", False):
            return ["http://disqus.com/forums/brettaylor/embed.js"]
        return None


settings = {
    "blog_title": u"Bret Taylor's blog",
    "template_path": os.path.join(os.path.dirname(__file__), "templates"),
    "ui_modules": {"Entry": EntryModule},
    "xsrf_cookies": True,
    "debug": os.environ.get("SERVER_SOFTWARE", "").startswith("Development/"),
}
application = tornado.wsgi.WSGIApplication([
    (r"/", HomeHandler),
    (r"/archive", ArchiveHandler),
    (r"/feed", FeedHandler),
    (r"/entry/([^/]+)/?", EntryHandler),
    (r"/compose", ComposeHandler),
    (r"/about", AboutHandler),
    (r"/index", tornado.web.RedirectHandler, {"url": "/archive"}),
], **settings)


def main():
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == "__main__":
    main()
