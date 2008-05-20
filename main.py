#!/usr/bin/env python

import web

urls = (
  '/', 'index'
)

render = web.template.render('templates/')

class index:
    def GET(self):
        return render.index()
        
app = web.application(urls, globals())
main = app.cgirun()