#!/usr/bin/env python

import cgi, logging, random, re, wsgiref.handlers

from betterhandler import *
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from google.appengine.api import memcache

HTTPRE = re.compile('http:\/\/')
DOWNRE = re.compile('downforeveryoneorjustme')

def valid_response_code(code):
  if (code == 200) or (code == 301) or (code == 302):
    return True
  else:
    return False
  
class Url:
  def __init__(self, domain):
    if domain.find("http%3A//") is not -1:
      domain = domain.split("http%3A//")[1]
    
    self.original_domain = domain
    self.domain = self.clean_url(domain)
    logging.debug("new Url: <original_domain: %s> <domain: %s>", self.original_domain, self.domain)
    
  def clean_url(self, domain):
    domain = cgi.escape(domain)
    domain.encode("utf-8")

    if HTTPRE.match(domain) == None:
      domain = 'http://' + domain

    return domain
    
  def dos(self):
    doscheck = memcache.get(self.domain)
    
    if doscheck is not None:
      doscheck = memcache.incr(self.domain)
    else:
      doscheck = memcache.add(self.domain, 0, 60)
      
      if not doscheck:
        logging.error("Memcache set failed.")
        
      doscheck = 0
    
    if doscheck > 500:
      return True
    else:
      return False
      
  def isself(self):
    logging.debug("in isself domain is %s", self.domain)
    
    if DOWNRE.search(self.domain) == None:
      return False
    else:
      return True

class FrontPage(BetterHandler):
  def get(self):
    for_template = {
      'title': 'Down for everyone or just me?',
    }
    return self.response.out.write(template.render(self.template_path('index.html'), for_template))

class CheckDomain(BetterHandler):
  def render_error(self, url, error='unknown'):
    for_template = {
      'title': 'Huh?',
      'domain': url.original_domain,
    }
    logging.error("Error on domain '%s': %s", url.domain, error)
    return self.response.out.write(template.render(self.template_path('error.html'), for_template))
  
  def render_down(self, url):
    for_template = {
      'title': "It's not just you!",
      'domain': url.domain,
      'original_domain': url.original_domain,
    }
    return self.response.out.write(template.render(self.template_path('down.html'), for_template))
  
  def render_up(self, url):
    for_template = {
      'title': "It's just you.",
      'domain': url.domain,
      'original_domain': url.original_domain,
    }
    return self.response.out.write(template.render(self.template_path('up.html'), for_template))
  
  def render_hurr(self):
    for_template = {
      'title': "It's just you.",
    }
    return self.response.out.write(template.render(self.template_path('hurr.html'), for_template))
  
  def get(self, domain):
    u = Url(domain)
                
    if u.isself():
      self.render_hurr()
    elif u.dos():
      self.render_error(u, "potential DoS")
    else:        
      try:
        response = urlfetch.fetch(u.domain, method=urlfetch.HEAD)
      except urlfetch.Error:
        self.render_down(u)
      except urlfetch.InvalidURLError:
        self.render_error(u, "urlfetch.InvalidURLError")
      except DeadlineExceededError:
        self.render_down(u)
      else:
        if valid_response_code(response.status_code):
          self.render_up(u)
        else:
          self.render_down(u)

def main():
    application = webapp.WSGIApplication([('/', FrontPage),
                                          (r'/(.*)', CheckDomain)],
                                         debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()
