from google.appengine.ext import db

class Downer(db.Model):
  domain = db.StringProperty(required=True)
  down_at = db.DateTimeProperty(auto_now_add=True)
