#!/usr/bin/env python

import base64, cgi, logging, urllib, wsgiref.handlers
from datetime import *
from itertools import *

from downer import *

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch


class DownerClear(webapp.RequestHandler):
  def get(self):
    hour_ago = datetime.now() + timedelta(minutes=-60)
    cleared = 0

    query = db.GqlQuery("SELECT __key__ FROM Downer WHERE down_at < :1", hour_ago)
    results = query.fetch(500)
    results_size = len(results)
    db.delete(results)
    cleared += results_size

    return self.response.out.write("cleared %d" % cleared)


def main():
    application = webapp.WSGIApplication([('/_downerclear', DownerClear)],
                                         debug=True)
    wsgiref.handlers.CGIHandler().run(application)