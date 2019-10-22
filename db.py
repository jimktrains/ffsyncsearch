#!/usr/bin/env python3

import psycopg2
import psycopg2.extras
from functools import reduce

def login(config):
    conn = psycopg2.connect(
        dbname=config['db']['dbname'],
        host=config['db']['host'],
        port=config['db']['port'],
        user=config['db']['user'],
        password=config['db']['password']
    )
    conn.autocommit = True
    return conn

class BookmarkInserter:
    """
    The reason for this is because the bookmarks aren't given in a way
    that's topologically sorted, and because I'm lazy, I'm just going to
    update the parent later.
    """
    def __init__(self, conn):
        self.conn = conn
    def __enter__(self):
        self.parents = {}
        self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.insert_bookmark_parents()
        self.cursor.close()

    def insert(self, bookmark):
        insert_data = {
            'type': None,
            'title': None,
            'dateAdded': None,
            'deleted': False,
            'modified': None,
        }
        insert_data.update(bookmark)

        # These could be potentially batched, but, we'll cross that bridge
        # if this becomes a problem. Ideally if we're only grabbing new
        # things then this shouldn't be an issue.
        self.cursor.execute("""
            INSERT INTO bookmark_entry 
            (bookmark_entry_id, bookmark_type, title, date_added, deleted, modified)
            VALUES
            (%(id)s, %(type)s, %(title)s, TO_TIMESTAMP(%(dateAdded)s/1000), %(deleted)s, TO_TIMESTAMP(%(modified)s))
            ON CONFLICT(bookmark_entry_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    modified = EXCLUDED.modified
        """, insert_data)
        i = len(self.parents)
        if 'parentid' in bookmark and bookmark['parentid'] not in ['places', 'unfiled']:
            self.parents[f"child_{i}"] = bookmark['id']
            self.parents[f"parent_{i}"] = bookmark['parentid']

    def insert_bookmark_parents(self):
        """
        Since mass updates from literals isn't quite a thing in SQL,
        let's create a temp table using a CTE, fill it, and do a mass update
        via a joined update query.

        While I'm OK doing the inserts one-at-a time because I don't already
        have a list of everything, I have a list of everything here and
        updates in a loop pain me.
        """
        if len(self.parents) < 1:
            return
        sql  = f"WITH bookmark_parent AS ("
        sql += " UNION ".join(map(lambda i: f"SELECT %(child_{i})s as childid, %(parent_{i})s as parentid", range(0,len(self.parents),2)))
        sql += f") UPDATE bookmark_entry SET parent_id = parentid FROM bookmark_parent WHERE bookmark_entry_id = childid"
        self.cursor.execute(sql, self.parents);

class HistoryInserter:
    def __init__(self, conn):
        self.conn = conn
    def __enter__(self):
        self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()

    def insert(self, history_entry):
        def reducer(c, e):
            if c is None:
                return e['date']
            return min(c, e['date'])

        insert_data = {
            'last_visited': None,
            'histUri': None,
            'visit_count': None,
            'title': None,
            'deleted': False,
        }
        insert_data.update(history_entry)

        if 'visits' in history_entry:
            insert_data['last_visited'] = reduce(reducer, history_entry['visits'], None)
            insert_data['visit_count'] = len(history_entry['visits'])
            del insert_data['visits']

        self.cursor.execute("""
            INSERT INTO history
            (history_id , last_visited, visit_count, title, url, deleted, modified)
            VALUES
            (%(id)s, TO_TIMESTAMP(%(last_visited)s/1000000), %(visit_count)s, %(title)s, %(histUri)s, %(deleted)s, TO_TIMESTAMP(%(modified)s))
            ON CONFLICT(history_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    last_visited = EXCLUDED.last_visited,
                    visit_count = EXCLUDED.visit_count,
                    modified = EXCLUDED.modified
        """, insert_data)

def get_history_for_text(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        # TODO: It might be best to move this into a table.
        domains_to_ignore = [
            # No textual content to scrape
            'openstreetmap.org',
            # Domains that'll always fail or otherwise unwanted
            'msqc.com',
            'localhost',
            'duckduckgo.com',
            'google.com',
            'trello.com',
            'paypal.com',
            'ebay.com',
            'amazon.com',
            'www.expedia.com',
            'craigslist.org',
            'chase.com',
            'citi.com',
            'pnc.com',
            # URLs that'll always fail or otherwise unwanted
            'wp-admin',
            'wp-login',
            # internal extension pages
            'moz-extension://',
            # CDNs (usually direct image links)
            'i.ebayimg.com'
            'googleusercontent',
            'pbs.twimg.com',
            'i.imgur.com',
            'dropboxusercontent',
            'us.archive.org',
            # These just hang?
            'lowes.com',
            'www.homedepot.com',
            # Misbehaves
            'www.appliancesconnection.com',
        ]
        ignored = " AND ".join(map(lambda x: f"url NOT LIKE '%{x}%'", domains_to_ignore))
        cursor.execute(f"SELECT history.* FROM history LEFT JOIN history_url_text USING (history_id) WHERE history_url_text.history_id IS NULL AND {ignored}")
        return cursor.fetchall()

def insert_url_text(conn, url_text):
    insert_data = {
        'raw_text': None,
        'processed_text': None,
        'title': None,
        'headers': None,
    }
    insert_data.update(url_text)

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("""
            INSERT INTO history_url_text
            (history_id , raw_text, processed_text, title, headers, http_status)
            VALUES
            (%(history_id)s, %(raw_text)s, %(processed_text)s, %(title)s, %(headers)s, %(http_status)s)
            ON CONFLICT(history_id)
                DO UPDATE SET 
                    title = EXCLUDED.title, 
                    raw_text = EXCLUDED.raw_text, 
                    processed_text = EXCLUDED.processed_text, 
                    headers = EXCLUDED.headers,
                    http_status = EXCLUDED.http_status
        """, insert_data)

def last_history_time(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("SELECT max(modified) AS last_visited FROM history")
        max_lv = cursor.fetchone()
        return max_lv['last_visited']

def search_text(conn, search_query):
    sql = """SELECT *,
       (processed_text_rank + (title_rank * 10) + (headers_rank * 5)) AS rank
FROM (
  SELECT history.*,
          ts_rank_cd(processed_text_tsv, query) AS processed_text_rank,
          ts_rank_cd(title_tsv, query) AS title_rank,
          ts_rank_cd(headers_tsv, query) AS headers_rank
   FROM history
   CROSS JOIN plainto_tsquery(%s) query
   JOIN history_url_text USING (history_id)
   WHERE processed_text_tsv @@ query
     OR title_tsv @@ query
     OR headers_tsv @@ query
) SEARCH
ORDER BY rank DESC
"""
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute(sql, (search_query,))
        return cursor.fetchall()
