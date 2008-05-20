#!/usr/bin/env python

import cgi, re 
from betterhandler import *
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
import wsgiref.handlers

HTTPRE = re.compile('http:\/\/')
DOWNRE = re.compile('downforeveryoneorjustme\.com')

def clean_url(domain):
    domain = cgi.escape(domain)
    domain.encode("utf-8")    
    
    if HTTPRE.match(domain):
        domain = 'http://' + domain
    
    return domain
    
def render_errorpage():
    for_template = {
        'title': 'Huh?',
    }
    
    self.response.out.write(template.render(self.template_path('error.html'), for_template))

class FrontPage(BetterHandler):
    def get(self):        
        for_template = {
            'title': 'Down for everyone or just me?',
        }
        
        self.response.out.write(template.render(self.template_path('index.html'), for_template))


class CheckDomain(BetterHandler):
    def get(self, domain):  
        domain = clean_url(domain)
        
        if DOWNRE.match(domain):
            for_template = {
                'title': "It's just you.",
            }
            
            self.response.out.write(template.render(self.template_path('hurr.html'), for_template))
        
        try:
            response = urlfetch.fetch(domain, method='HEAD')
        except urlfetch.Error:
            render_errorpage()
        except urlfetch.InvalidURLError:
            render_errorpage()
        else:
            status = response.status_code
              
        if (status == 200) or (status == 301) or (status == 302):
            for_template = {
                'title': "It's just you.",
                'domain': domain,
            }
            
            self.response.out.write(template.render(self.template_path('up.html'), for_template))
        else:
            for_template = {
                'title': "It's just you.",
            }
            
            self.response.out.write(template.render(self.template_path('down.html'), for_template))
            
        
def main():
    application = webapp.WSGIApplication([
                                            ('/', FrontPage),
                                            (r'/(.*)', CheckDomain)
                                         ],
                                         debug=True)

    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()