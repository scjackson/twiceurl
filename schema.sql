drop table if exists urls;
create table urls (
  id integer unique not null,
  full_url text unique not null
);

drop table if exists valid_ids;
create table valid_ids (
  id integer unique not null
);