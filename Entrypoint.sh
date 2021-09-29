#!/bin/sh
# The entrypoint script for docker container.
# Assumes the main python script resides at ./Src/MgmtWebSvc.py

cd Src || { echo "Missing Src dir"; exit; }

[ -z "$UWSGI_UID" ] && UWSGI_UID=nobody
[ -z "$UWSGI_GID" ] && UWSGI_GID=nogroup

[ -z "$PORT" ] && PORT=8083

#create db dir, in case it's missing
[ ! -d "${DB_DIR}" ] && mkdir -p "$DB_DIR"
chown ${UWSGI_UID}:${UWSGI_GID} "${DB_DIR}"

#default plugins list
UWSGI_PLUGINS="python3"

#there are three supported listen types:
#1. https (default): if ${UWSGI_HTTPS} environment variable or no ${UWSGI_HTTPS}, ${UWSGI_HTTP} and ${UWSGI_SOCKET}
#   are defined
#2. http: if ${UWSGI_HTTP} defined
#3. unix socket: if ${UWSGI_SOCKET}
#
#The last two modes should really be used with a ssl termination in front (such as nginx)
if [ -n "${UWSGI_HTTPS}" ] || { [ -z "${UWSGI_SOCKET}" ] && [ -z "${UWSGI_HTTP}" ]; }; then
  LISTEN_MODE="https"
elif [ -n "${UWSGI_HTTP}" ]; then
    LISTEN_MODE="http"
else
  LISTEN_MODE="unix"
fi

#add http plugin in case the proper env. var is set
[ -n "${UWSGI_HTTP}" ] && UWSGI_PLUGINS="http,${UWSGI_PLUGINS}"

#generate host certs if they missing and https mode is set
[ "$LISTEN_MODE" = "https" ] && {
    #generate certs if they're missing
    . ../PyVenv/bin/activate; python3 MgmtWebSvc.py --init-certs >>/tmp/LinyInitCerts.log 2>&1; deactivate;
    EXTRA_PARAMS="--https-socket ${HOST}:${PORT},${CERTS_DIR}/${HOST}-${PORT}.crt,${CERTS_DIR}/${HOST}-${PORT}.key";
  }

#some defaults
[ -z "${UWSGI_WORKERS}" ] && EXTRA_PARAMS="${EXTRA_PARAMS} --workers 8"

#finally run the uwsgi server
exec uwsgi --plugin ${UWSGI_PLUGINS} --wsgi-file MgmtWebSvcApp.py --callable g_theApp --virtualenv ${WORK_DIR}/PyVenv\
 --master --cheaper-algo spare --cheaper 1 --cheaper-initial 1 -l "${MAX_LISTEN_CONN-128}" --uid $UWSGI_UID\
 --gid $UWSGI_GID ${EXTRA_PARAMS}
