#!/usr/bin/env python

import base64, cgi, logging, urllib, wsgiref.handlers
from datetime import *
from itertools import *

from downer import *

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import memcache
from google.appengine.api import urlfetch

class DownError(Exception):
  pass

def get_top_domain():
  five_minutes_ago = datetime.now() + timedelta(minutes=-5)
  query = db.GqlQuery("SELECT * FROM Downer WHERE down_at >= :1", five_minutes_ago)
  results = query.fetch(1000)

  domains = []

  for result in results:
    domains.append(result.domain)

  grouped_domains = dict([(a, len(list(b))) for a, b in groupby(sorted(domains))])
  sorted_domains = sorted(grouped_domains.items(), reverse=True)

  if len(sorted_domains) > 0:
    return sorted_domains[0][0]
  else:
    raise DownError, "No domains recorded down"


def tweet(msg):
  url = "https://twitter.com/statuses/update.json"
  username = "downfor"
  password = "foobar23"

  form_fields = { "status": msg }
  payload = urllib.urlencode(form_fields)

  authheader =  "Basic %s" % base64.encodestring('%s:%s' % (username, password))
  base64string = base64.encodestring('%s:%s' % (username, password))[:-1]
  authheader =  "Basic %s" % base64string

  result = urlfetch.fetch(url=url, payload=payload, method=urlfetch.POST,
                          headers={"Authorization": authheader})

  if int(result.status_code) == 200:
    return 200
  else:
    raise DownError, result.status_code


class TweetCheck(webapp.RequestHandler):
  def get(self):
    try:
      current_top_domain = get_top_domain()
    except DownError, e:
      return self.response.out.write("Exception: %s" % e)

    last_top_domain = memcache.get("topdomain")

    if current_top_domain != last_top_domain:
      memcache.set("topdomain", current_top_domain)

      try:
        tweet("%s looks like it might be down." % current_top_domain)
      except DownError, e:
        return self.response.out.write("Exception: couldn't tweet, got a %s" % e)

      return self.response.out.write("New top domain: %s" % current_top_domain)
    else:
      return self.response.out.write("Same old top domain: %s" % last_top_domain)


def main():
    application = webapp.WSGIApplication([('/_tweetcheck', TweetCheck)],
                                         debug=True)
    wsgiref.handlers.CGIHandler().run(application)