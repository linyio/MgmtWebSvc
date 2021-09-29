FROM alpine
LABEL maintainer="Admin <admin@liny.io>"\
    vendor="Liny"

# It's preferable to display a build timestam on swagger documentation version for distinguish among various versions.
# For that, build the docker image as:
# docker build -t linyio/ovpn-users-restapi --build-arg VERSION_EXTRA=" - $(date '+%Y-%m-%d %H:%M:%S')" .
ARG VERSION_EXTRA=""
ENV RUN_BASE_DIR="/var/run/MgmtWebSvc"
ENV DB_DIR="${RUN_BASE_DIR}/Db"
ENV CERTS_DIR="${RUN_BASE_DIR}/Certs"

# To enable stats run with -e UWSGI_STATS=[<host>]:<tcp_port> or -e UWSGI_STATS=<unix_socket_path>
# To change the uwsgi socket run the docker container with -e UWSGI_SOCKET=[<host>]:<tcp_port> or
#   -e UWSGI_SOCKET=<unix_socket_path>
# To enable http (which will automatically disable uwsgi socket) run with -e UWSGI_HTTP=[<host>]:<tcp_port>
# To specify workers nunmber run with -e UWSGI_WORKERS=<workers_no>
# For the moment disable swagger documentation
ENV DOC=OFF
ENV WORK_DIR="/opt/MgmtWebSvc"
ENV DB_PATH="${DB_DIR}/db.sqlite"
ENV DB_URL="sqlite:///$DB_PATH"

WORKDIR ${WORK_DIR}
# SHELL ["/bin/sh", "-c"]
COPY requirements-docker.txt ${WORK_DIR}/
COPY Src ${WORK_DIR}/Src
COPY Entrypoint.sh ${WORK_DIR}/
ENV VERSION_EXTRA=$VERSION_EXTRA

RUN apk update &&\
    apk add --no-cache uwsgi-python3 uwsgi-http openvpn &&\
    apk add --no-cache --virtual liny-build_pkgs build-base python3-dev libffi-dev openssl-dev rust cargo &&\
    python3 -m venv --system-site-packages PyVenv &&\
    source PyVenv/bin/activate &&\
    pip install --upgrade pip &&\
    pip install --upgrade -r requirements-docker.txt &&\
    apk del liny-build_pkgs &&\
    rm -R /root/.cache &&\
    chmod a+x ${WORK_DIR}/Entrypoint.sh

CMD ["./Entrypoint.sh"]

