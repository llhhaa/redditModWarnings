# bot that keeps track of moderator warnings and links them in posts in a mods-only sub
# thank you /u/GoldenSights for the base code!
import traceback
import praw # simple interface to the reddit API, also handles rate limiting of requests
import time
import sqlite3
import configparser

'''USER CONFIGURATION'''

# config setup
configParser = configparser.RawConfigParser()
configPath = 'd:\\repos\\redditModWarnings\\config.txt'
configParser.read(configPath)

# config - the following values are changed in config.txt
APP_ID = configParser.get('config', 'id')
APP_SECRET = configParser.get('config', 'secret')
APP_URI = configParser.get('config', 'uri')
APP_REFRESH = configParser.get('config', 'refresh')
APP_SCOPES = configParser.get('config', 'scopes')
# https://www.reddit.com/comments/3cm1p8/how_to_make_your_bot_use_oauth2/

USERAGENT = configParser.get('config', 'useragent')
# This is a short description of what the bot does.

SUBREDDIT = configParser.get('config', 'subreddit')
# This is the sub or list of subs to scan for new comments. For a single sub, use "sub1". For multiple subreddits, use "sub1+sub2+sub3+..."

TARGETSUB = configParser.get('config', 'targetsub')
# This is the to which warnings will be posted.

KEYWORD1 = configParser.get('config', 'keyword1')
KEYWORDS = [KEYWORD1]
# These are the words you are looking for

MAXPOSTS = 100
# This is how many comments you want to retrieve all at once. PRAW can download 100 at a time.

WAIT = 30
# This is how many seconds you will wait between cycles. The bot is completely inactive during this time.

CLEANCYCLES = 10
# After this many cycles, the bot will clean its database
# Keeping only the latest (2*MAXPOSTS) items

'''All done!'''

try:
    import bot
    USERAGENT = bot.aG
except ImportError:
    pass

print('Opening SQL Database')
sql = sqlite3.connect('sql.db')
cur = sql.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS oldcomments(id TEXT)')

print('Logging in...')
r = praw.Reddit(USERAGENT)
r.set_oauth_app_info(APP_ID, APP_SECRET, APP_URI)
r.refresh_access_information(APP_REFRESH)

def warningBot():
    print('Searching %s.' % SUBREDDIT)
    subreddit = r.get_subreddit(SUBREDDIT)
    mods = r.get_moderators(SUBREDDIT)
    comments = []
    comments = list(subreddit.get_comments(limit=MAXPOSTS))
    comments.sort(key=lambda x: x.created_utc)

    for comment in comments:
        # Anything that needs to happen every loop goes here.
        cid = comment.id

        try:
            cauthor = comment.author.name
        except AttributeError:
            # Author is deleted. We don't care about this comment.
            continue

        try:
            parent = r.get_info(thing_id=comment.parent_id)
        except AttributeError:
            # Parent doesn't exist. We don't care about this comment.
            continue

        if cauthor.lower() == r.user.name.lower():
            # Don't reply to yourself, robot!
            print('Will not reply to myself.')
            continue

        #if mods != [] and all(auth.lower() != cauthor for auth in mods):
            # comment was not made by a subreddit mod
            #continue

        if not comment.distinguished == 'moderator':
            # comment was not distinguished
            continue

        cur.execute('SELECT * FROM oldcomments WHERE ID=?', [cid])
        if cur.fetchone():
            # comment is already in the database
            continue

        cbody = comment.body
        cbody = cbody.lower()
        # get comment text

        if not any(key.lower() in cbody for key in KEYWORDS):
            # Does not contain our keyword
            continue

        splitcbody = cbody.split(":")
        if not type(splitcbody) is list:
            continue
        if len(splitcbody) > 2:
            continue
            # comment was not correctly formatted

        cur.execute('INSERT INTO oldcomments VALUES(?)', [cid])
        sql.commit()

        print('Submitting for %s by %s to %s' % (cid, cauthor, TARGETSUB))
        pauthor = parent.author.name
        modnotes = splitcbody[1]

        modnotestitle = (modnotes[:260] + '...') if len(modnotes) > 260 else modnotes
        # if modnotes is longer than 260, truncate it

        wtitle = 'Warning for %s: %s' % (pauthor, modnotestitle)
        wtext = 'Warning has been issued to %s for [this comment](%s). Mod notes: %s' % (pauthor, parent.permalink, modnotes)
        try:
            # comment.reply(wtext)
            r.submit(TARGETSUB, wtitle, text=wtext)
        except praw.errors.Forbidden:
            print('403 FORBIDDEN - is the bot banned from %s?' % comment.subreddit.display_name)

cycles = 0
while True:
    try:
        warningBot()
        cycles += 1
    except Exception as e:
        traceback.print_exc()
    if cycles >= CLEANCYCLES:
        print('Cleaning database')
        cur.execute('DELETE FROM oldcomments WHERE id NOT IN (SELECT id FROM oldcomments ORDER BY id DESC LIMIT ?)', [MAXPOSTS * 2])
        sql.commit()
        cycles = 0
    print('Running again in %d seconds \n' % WAIT)
    time.sleep(WAIT)
