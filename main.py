#!/usr/bin/env python

import web, cgi, re 
from google.appengine.api import urlfetch

urls = (
  '/', 'index',
  '/(.*)', 'check'
)

render = web.template.render('templates/')

HTTPRE = re.compile('http:\/\/')
DOWNRE = re.compile('downforeveryoneorjustme\.com')

def clean_url(domain):
    domain = cgi.escape(domain)
    domain.encode("utf-8")    
    
    if HTTPRE.match(domain):
        domain = 'http://' + domain
    
    return domain
    
def render_errorpage():
    title = "Huh?"
    output = render.error()
    return render.layout(output, title)

class index:
    def GET(self):
        title = 'Down for everyone or just me?'
        output = render.index()
        return render.layout(output, title)

class check:
    def GET(self, domain):  
        domain = clean_url(domain)
        
        if DOWNRE.match(domain):
            title = "It's just you."
            output = render.hurr()
            return render.layout(output, title)            
        
        try:
            response = urlfetch.fetch(domain, method='HEAD')
        except urlfetch.Error:
            render_errorpage()
        except urlfetch.InvalidURLError:
            render_errorpage()
        else:
            status = response.status_code
              
        if (status == 200) or (status == 301) or (status == 302):
            title = "It's just you."
            output = render.up(domain)
        else:
            title = "It's not just you!"
            output = render.down(domain)
            
        return render.layout(output, title)
        
        
app = web.application(urls, globals())
main = app.cgirun()