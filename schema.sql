create extension pg_trgm;

drop role if exists ffsync;
create role ffsync with login password 'ffsync123';
grant all on database ffsync to ffsync;

set role ffsync;

create table history (
  history_id text primary key,
  icon text,
  last_visited timestamp,
  visit_count integer,
  title text,
  url text unique,
  deleted boolean not null default false
);

create table history_url_text (
  history_id text primary key references history,
  raw_text text,
  processed_text text,
  title text,
  headers text,
  deleted boolean not null default false
);
create index on history_url_text using gin (to_tsvector('english', processed_text));
create index on history_url_text using gin (to_tsvector('english', title));
create index on history_url_text using gin (to_tsvector('english', headers));

create index on history_url_text using gist (processed_text gist_trgm_ops);
create index on history_url_text using gist (title gist_trgm_ops);
create index on history_url_text using gist (headers gist_trgm_ops);

create table bookmark_entry (
  bookmark_entry_id text primary key,
  icon text,
  date_added timestamp,
  title text,
  bookmark_type text,
  parent_id text references bookmark_entry,
  url text
);

create table bookmark_tag (
  bookmark_tag_id serial primary key,
  tag text not null unique
);
create index on bookmark_tag using gist (tag gist_trgm_ops);

create table bookmark_entry_tag (
  bookmark_tag_id integer references bookmark_tag,
  bookmark_entry_id text references bookmark_entry,
  primary key (bookmark_tag_id, bookmark_entry_id),
  unique (bookmark_entry_id, bookmark_tag_id)
);
