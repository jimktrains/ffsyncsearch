create table history (
  history_id serial primary key,
  icon text,
  last_visited timestamp,
  title text,
  url text,
);

create table history_url_text (
  history_id integer unique references history,
  raw_text text,
  processed_text text
);
create index on history_url_text using gin (to_tsvector('english', processed_text));

create table bookmark_entry (
  bookmark_entry_id serial primary key,
  ff_id text unique,
  icon text,
  date_added timestamp,
  title text,
  bookmark_type text,
  parent_ff_id text references bookmark(ff_id),
  bmk_uri text,
);

create table bookmark_tag (
  bookmark_tag_id serial primary key,
  tag text not null unique
);

create table bookmark_entry_tag (
  bookmark_tag_id integer references bookmark_tag,
  bookmark_entry_id integer references bookmark_entry,
  primary key (bookmark_tag_id, bookmark_entry_id)
);
