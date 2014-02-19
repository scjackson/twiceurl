This is a URL shortener written in Flask that uses SQLite as a backend. I did not put much (really any) time into the front end other than to get it to work... So it's not the prettiest

To run on Ubuntu:

Install Dependencies:

    sudo apt-get install python
    sudo apt-get install sqlite3
    sudo apt-get install python-flask
    sudo apt-get install python-pip
    sudo pip install Flask --upgrade
    sudo pip install Flask-Script

Clone repo and navigate to directory

To start server:
    python twiceurl.py

To populate cached id values (this is not necessary to successfully us the service. the idea is that this script would be executed by a cronjob to maintain a list of quickly accessible urls):

    python manage.py populate

To use the site locally:
    http://127.0.0.1:5000/