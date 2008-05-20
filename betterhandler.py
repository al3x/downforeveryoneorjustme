import os
from google.appengine.ext import webapp

class BetterHandler(webapp.RequestHandler):
    def template_path(self, filename):
        return os.path.join(os.path.dirname(__file__), 'templates', filename)
