# manage.py

from flask.ext.script import Manager

from twiceurl import app
from twiceurl import populate_valid_ids

manager = Manager(app)

#function to be run in background that will find and add unused ids
#purpose is to reduce the time of user request for url creation 
@manager.command
def populate():
  	populate_valid_ids()

if __name__ == "__main__":
    manager.run()