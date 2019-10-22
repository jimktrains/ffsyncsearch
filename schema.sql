create extension pg_trgm;

drop role if exists ffsync;
create role ffsync with login password 'ffsync123';
grant all on database ffsync to ffsync;
grant all on all tables in schema public to ffsync;
grant all on all sequences in schema public to ffsync;

set role ffsync;

create table history_entry (
  history_entry_id text primary key,
  last_visited timestamp,
  visit_count integer,
  title text,
  url text,
  clean_url text,
  modified timestamp,
  deleted boolean not null default false,
  domain text generated always as (split_part(split_part(url, '/', 3), ':', 1)) stored
);
create index on history_entry(domain);
create index on history_entry using gist (url gist_trgm_ops);
create index on history_entry using gist (title gist_trgm_ops);

create table bookmark_entry (
  bookmark_entry_id text primary key,
  date_added timestamp,
  title text,
  bookmark_type text,
  parent_id text references bookmark_entry,
  url text,
  clean_url text,
  modified timestamp,
  deleted boolean default false
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

create table url_text (
  url_text_id serial primary key,
  url text not null unique,
  raw_text text,
  processed_text text,
  title text,
  headers text,
  http_status int,
  processed_text_tsv tsvector generated always as (to_tsvector('english', processed_text)) stored,
  title_tsv tsvector generated always as (to_tsvector('english', title)) stored,
  headers_tsv tsvector generated always as (to_tsvector('english', headers)) stored
);
create index on url_text using gin (processed_text_tsv);
create index on url_text using gin (title_tsv);
create index on url_text using gin (headers_tsv);
create index on url_text using gist (title gist_trgm_ops);
create index on url_text using gist (headers gist_trgm_ops);

create table history_entry_url_text (
  url_text_id int not null references url_text,
  history_entry_id text not null references history_entry,
  primary key (url_text_id, history_entry_id),
  unique (history_entry_id, url_text_id)
);

create table bookmark_entry_url_text (
  url_text_id int not null references url_text,
  bookmark_entry_id text not null references bookmark_entry,
  primary key (url_text_id, bookmark_entry_id),
  unique (bookmark_entry_id, url_text_id)
);
