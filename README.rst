My FireFox Sync
---------------

Create a searchable archive from my my bookmarks and history. Too often
I find I can't quite google something or there is a lot of noise in FF's
history sidebar.

config.ini
----------

Sample: ::

    [user]
    email=address@example.com
    password=super_secret
    
    [db]
    dbname=database_name
    host=host_name_or_ip_or_socket
    port=port
    user=user_role
    password=super_secret


Files
-----

* `sync.py` - Start of the main syncing service
* `auth.py` - Handles authentication
* `utils.py` - Handles API calls to get and decrypt collctions and items
* `schema.sql` - Initial thoughts on the schema to store this to
* `Makefile` - Build a new DB
* `page_fetcher.py` - Fetches the page text to place into the db
* `search.py` - Example full-text search
