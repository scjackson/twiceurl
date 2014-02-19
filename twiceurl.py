import os, string, math, random, urlparse
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, session, redirect, url_for, g, render_template

app = Flask(__name__)

#set up application wide config options
app.config.update(dict(
      DATABASE = os.path.join(app.root_path, 'twiceurl.db'),
      DEBUG = True,
      SECRET_KEY = 'development key',
      USERNAME = 'admin',
      PASSWORD = 'default',
      ALPHABET_SIZE = 62,
      MAX_CHARACTERS = 4,
      MIN_INT = 0,
      MAX_INT = math.pow(62, 4),
      ID_WINDOW = 1000,
      ALPHABET = list(string.ascii_lowercase + string.ascii_uppercase + string.digits),
      ALPHABET_DICT = {key: value for key, value in zip(
          list(string.ascii_lowercase + string.ascii_uppercase + string.digits), 
          range(0, 62)
      )},
      NUMBER_CACHED_IDS = 20
  )
)

######################################################
########### DATABASE CONNECTION FUNCTIONS ############
######################################################

#Connects to the specific database
def connect_db():
  rv = sqlite3.connect(app.config['DATABASE'])
  rv.row_factory = sqlite3.Row
  return rv

#Creates the database tables
def init_db():
  with app.app_context():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
      db.cursor().executescript(f.read())
    db.commit()

#Opens a new database connection if there is none yet for the
#current application context.
def get_db():
  if not hasattr(app, 'sqlite_db'):
    g.sqlite_db = connect_db()
  return g.sqlite_db

#Closes the database again at the end of the request
@app.teardown_appcontext
def close_db(error):
  if hasattr(app, 'sqlite_db'):
    g.sqlite_db.close() 


######################################################
################# ROUTING FUNCTIONS ##################
######################################################

#Homepage
@app.route('/')
def new_url():
  return render_template('new_url.html')

#Informational page about a given short url
@app.route('/url/<short_url>')
def url_information (short_url):
  url_result = look_up_by_url(short_url, "")
  if (len(url_result) == 0):
    return render_template('not_found.html')
  return render_template(
      'url_information.html', 
      short_url= convert_to_base62(url_result[0]["id"]),
      full_url=url_result[0]["full_url"]
  )

#Create URL action -- no user facing display
@app.route('/create', methods=['POST'])
def create_url():

  #if the input is empty, just take them back to the homepage
  url_request = request.form['full_url']

  #do some basic checking to see if the url is in the right format
  url_request = urlparse.urlparse(url_request, scheme="http")
  if (url_request.netloc == ""):
    return render_template(
        'new_url.html',
        full_url=request.form['full_url'], 
        bad_format=True
    )
  else:
    url_request = url_request.geturl()

    #check to see if we already have a short url for this request
    result = look_up_by_url("", url_request)
    if (len(result) > 0):
      return redirect(url_for('url_information', short_url=convert_to_base62(result[0]['id'])))

    #otherwise, we need to make a new entry
    else:

      #Attempt to use whats in the precomputed table, else generate a new one
      valid_id = get_cached_valid_id()
      if (valid_id > -1):
        insert_url(valid_id, url_request)
        delete_from_valid_ids(valid_id)
      else:

        #if this returns negative one, it means we are running out of urls.
        #if this was a real site, we'd probably want to expand the possible url 
        #combinations
        valid_id = find_valid_id()
        if valid_id == -1:
          return render_template(
            'new_url.html',
            full_url=request.form['full_url'], 
            server_error=True
          )
        else:
          insert_url (valid_id, url_request)
      return redirect(url_for('url_information', short_url=convert_to_base62(valid_id)))

#Catch all for url redirects -- take them to external url if valid, 404 if not
@app.route('/<path>')
def redirect_to_full_url (path):
  result = look_up_by_url(path, "")
  if (len(result)> 0):
    return redirect(result[0]['full_url'], code=302)
  else:
    return render_template('not_found.html')

#404 display
@app.route('/404')
def not_found ():
  return render_template('not_found.html')


######################################################
################ DB ACCESS FUNCTIONS #################
######################################################

#Get a cached if from the database
def get_cached_valid_id():
  db = get_db()
  id_cursor = db.execute(
      'SELECT id FROM valid_ids LIMIT 1'
  )
  result = id_cursor.fetchall()
  if (len(result) > 0):
    return result[0]['id']
  else:
    return -1

#add a url to the database
def insert_url (id, full_url):
  db = get_db()
  db.execute(
      'INSERT INTO urls (id, full_url) VALUES (?, ?)', 
      [id, full_url]
  )
  db.commit()

#remove a precomputed id from the cached table
def delete_from_valid_ids (id):
  db = get_db()
  db.execute(
      'DELETE FROM valid_ids WHERE id = ?', 
      [result[0]['id']]
  )
  db.commit()

#Look up a url by either its short string or by the url it maps to
def look_up_by_url (short_url, full_url):
  db = get_db()
  db_cursor = db.execute(
      'SELECT id, full_url FROM urls WHERE full_url = ? OR id = ?',
      [full_url, convert_from_base62(short_url)]
  )
  return db_cursor.fetchall()


#Find an random unused id within application specified range
def find_valid_id ():
  with app.app_context():

    #choose a random id to begin searching from
    randomID = random.randint(app.config['MIN_INT'], app.config['MAX_INT'] - 1)
    db = get_db()

    #retrieve all of the ids currently in use, or reserved for future use
    result = db.execute(
        'SELECT id FROM ('
        '  SELECT id FROM urls ' +
        '  WHERE (id >= ? AND id < ? + ?) OR ((? + ?) > ? AND id < ((? + ?) % ?)) ' +
        '  UNION ' + 
        '  SELECT id FROM valid_ids ' +
        '  WHERE (id >= ? AND id < ? + ?) OR ((? + ?) > ? AND id < ((? + ?) % ?)) ' +
        ') a ORDER BY CASE WHEN id >= ? THEN id ELSE id + ? + ? END ASC',
        ( randomID, 
          randomID,
          app.config['ID_WINDOW'],
          randomID, 
          app.config['ID_WINDOW'],
          app.config['MAX_INT'],
          randomID, 
          app.config['ID_WINDOW'],
          app.config['MAX_INT'],
          randomID, 
          randomID,
          app.config['ID_WINDOW'],
          randomID, 
          app.config['ID_WINDOW'],
          app.config['MAX_INT'], 
          randomID, 
          app.config['ID_WINDOW'],
          app.config['MAX_INT'], 
          randomID,
          randomID,
          app.config['ID_WINDOW']
        )
    )
    takenIDs = result.fetchall()

    #if we didn't find any results, just return whatever random number we generated
    if len(takenIDs) == 0:
      return randomID
    else:
      #take care of ids out of max int range
      currentIndex = randomID

      #check for gaps in the ids that are currently in use/reserved
      for takenID in takenIDs:
        if takenID["id"] != currentIndex:
          return currentIndex
        else: 
          currentIndex = (currentIndex + 1) % app.config['MAX_INT']

      #return -1 if we couldnt find anything... currently not elegantly handled in
      #the rest of the code
      return -1

#Add ids to the precomputed table if necessary
def populate_valid_ids():
  with app.app_context():
    db = get_db()
    result = db.execute('SELECT COUNT(*) AS count FROM valid_ids')
    resultCount = result.fetchall()

    #If we need to add some more ids, do so
    for x in range(0, app.config['NUMBER_CACHED_IDS'] - resultCount[0]["count"]):
      to_insert = find_valid_id()

      #-1 indicates that there were no available ids in the range we examined
      if (to_insert != -1):
        db.execute(
            'INSERT INTO valid_ids (id) VALUES (?)', 
            [to_insert]
        )
        db.commit()

######################################################
################# BASE 62 FUNCTIONS ##################
######################################################

#convert a base62 string (ex 'a3fa') to an integer
def convert_from_base62 (inputString):
  output = 0;
  for index, character in enumerate(list(inputString)):
    output += int(
        app.config['ALPHABET_DICT'][character] * math.pow(
            app.config['ALPHABET_SIZE'], 
            app.config['MAX_CHARACTERS'] - 1 - index
        )
    )
  return output

#convert an integer (ex 0) to a base 62 string (ex 'aaaa')
def convert_to_base62 (inputInteger):
  output = ""
  for x in range(app.config['MAX_CHARACTERS'] - 1, -1, -1):
    output += app.config['ALPHABET'][int(inputInteger/math.pow(app.config['ALPHABET_SIZE'], x))]
    inputInteger = inputInteger % math.pow(app.config['ALPHABET_SIZE'], x)
  return output
    
if __name__ == '__main__':
  init_db()
  app.run()