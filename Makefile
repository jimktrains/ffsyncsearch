all: clean install

# port 5434 is pg12 on my system
PORT=5434
PSQL_OPTS=-v ON_ERROR_STOP=1 -p ${PORT}
DB=ffsync

install:
	psql ${PSQL_OPTS} -f schema.sql ${DB}

clean:
	dropdb -p ${PORT} --if-exists ${DB}
	createdb -p ${PORT} ${DB}
