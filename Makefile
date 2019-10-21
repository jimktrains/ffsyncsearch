all: clean install

PSQL_OPTS=-v ON_ERROR_STOP=1
DB=ffsync

install:
	psql ${PSQL_OPTS} -f schema.sql ${DB}

clean:
	dropdb --if-exists ${DB}
	createdb ${DB}
