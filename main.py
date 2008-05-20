#!/usr/bin/env python

import cgi, re 
from betterhandler import *
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
import wsgiref.handlers
import logging

HTTPRE = re.compile('http:\/\/')
DOWNRE = re.compile('downforeveryoneorjustme')

def clean_url(domain):
    domain = cgi.escape(domain)
    domain.encode("utf-8")    
    
    if HTTPRE.match(domain) == None:
        domain = 'http://' + domain
    
    return domain
    
    
class FrontPage(BetterHandler):
    def get(self):        
        for_template = {
            'title': 'Down for everyone or just me?',
        }
        return self.response.out.write(template.render(self.template_path('index.html'), for_template))


class CheckDomain(BetterHandler):
    def get(self, domain):
        original_domain = domain
        domain = clean_url(domain)
        
        if DOWNRE.search(domain) is not None:
            for_template = {
                'title': "It's just you.",
            }
            return self.response.out.write(template.render(self.template_path('hurr.html'), for_template))
        
        try:
            response = urlfetch.fetch(domain, method=urlfetch.HEAD)
        except urlfetch.Error:
            for_template = {
                'title': 'Huh?'
            }
            logging.debug("urlfetch.Error for domain '%s'", domain)
            return self.response.out.write(template.render(self.template_path('error.html'), for_template))        
        except urlfetch.InvalidURLError:
            for_template = {
                'title': 'Huh?'
            }
            logging.debug("urlfetch.InvalidURLError for domain '%s'", domain)
            return self.response.out.write(template.render(self.template_path('error.html'), for_template))
        else:
            if (response.status_code == 200) or (response.status_code == 301) or (response.status_code == 302):
                for_template = {
                    'title': "It's just you.",
                    'domain': domain,
                    'original_domain': original_domain,
                }
                return self.response.out.write(template.render(self.template_path('up.html'), for_template))
            else:
                for_template = {
                    'title': "It's not just you!",
                    'domain': domain,
                    'original_domain': original_domain,
                }
                return self.response.out.write(template.render(self.template_path('down.html'), for_template))
            
        
def main():
    application = webapp.WSGIApplication([
                                            ('/', FrontPage),
                                            (r'/(.*)', CheckDomain)
                                         ],
                                         debug=True)

    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()