# Management web service
The management web service is the central piece of [Liny's](https://liny.io) VPN, used for storing sensitive informaion 
such as organizations, users and other VPN servers info. It is based on Python Flask restful micro-framework and it gets deployed as docker containers on user's trusted machines.    
 
## 1. Docker container

For the best management and security, the service is packaged as a docker container and exposed through https, http or [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/) with a ngingx as [reverse proxy](https://en.wikipedia.org/wiki/Reverse_proxy)). uWSGI server is designed to serve the service in production. A few configuration options will actually be related with it.

### Running the docker container
#### HTTPS
The https mode is the only mode which can securly expose the service on the internet, without the need of a ssl 
termination (such as nginx).

Run the docker as:
```
    sudo docker container run -d -p 444:444 -e USER_IDS=486ce768-1d41-4bcf-b49c-9a770e185994 
    -e HOST=mgmt-web-svc.example.com -e PORT=444 
    --hostname mgmt-web-svc.example.com -v LinyMgmtWebSvc-HostCerts:/var/run/MgmtWebSvc/Certs 
    -v LinyMgmtWebSvc-Db-mgmt-web-svc.example.com-444:/var/run/MgmtWebSvc/Db --name liny-mgmt-web-svc-444 
    linyio/mgmt-web-svc
```
with the following explanations:
* `-p 444:444`: exposed port (tcp 444 in this case)
* `-e USER_IDS=486ce768-1d41-4bcf-b49c-9a770e185994`: the user to be accepted in JWTs
* `--hostname mgmt-web-svc.example.com`: the container's hostname. It's really important, because it will be used by the service at listening
* `-v LinyMgmtWebSvc-HostCerts:/var/run/MgmtWebSvc/Certs`: the volume for storing certificates
* `-v LinyMgmtWebSvc-Db-mgmt-web-svc.example.com-444:/var/run/MgmtWebSvc/Db`: the volume for storing the db
* `--name liny-mgmt-web-svc-444`: container's name
* `linyio/mgmt-web-svc`: image name

#### uWSGI unix socket and nginx forward proxy
For launching the docker container with uWSGI unix socket and nginx proxy run:
```
docker container run -v /var/run/nginx:/var/run/uwsgi -v mgmt-web-svc:/var/run/MgmtWebSvc/Db 
--name mgmt-web-svc -e USER_IDS=486ce768-1d41-4bcf-b49c-9a770e185994 
-e UWSGI_SOCKET=/var/run/uwsgi/uwsgi.sock -e UWSGI_CHOWN_SOCKET="$(id -u nginx):$(id -g nginx)" 
-e SERVER_NAME="mgmt-web-svc.example.com" -d --restart=always linyio/mgmt-web-svc
```
with the following explanations:
* `-v /var/run/nginx:/var/run/uwsgi`: mounts the host's `/var/run/nginx` to the container's `/var/run/uwsgi` folder for storing the uWSGI unix socket socket. The unix sockets are best for speed and security. Make sure the `/var/run/nginx` host folder is owned and accessible by the user under which nginx runs
* `-v mgmt-web-svc:/var/run/MgmtWebSvc/Db`: the volume where the database (`db.sqlite`) resides and will survive to the multiple container's restarts/upgrades. The `/var/run/MgmtWebSvc/Db` is the default db path mapped within container. It can be changed with `DB_PATH` environment variable if sqlite database is still desired or specify an entire url, through the `DB_URL` environment variable with `sqlite:///$DB_PATH` schema. Note: only sqlite db was tested so far
* `-e USER_IDS=486ce768-1d41-4bcf-b49c-9a770e185994`: the user to be accepted in JWTs
* `-e UWSGI_SOCKET=/var/run/uwsgi/uwsgi.sock`: the location where the uwsgi unix socket resides. It must to closely match with the first volume - `-v /var/run/nginx:/var/run/uwsgi`
* `-e UWSGI_CHOWN_SOCKET="$(id -u nginx):$(id -g nginx)"`: sets the uWSGI unix sockets ownership. It has to be set to the uid and gid under which the nginx runs on the host
* `-e SERVER_NAME="mgmt-web-svc.example.com"`: it's like the container's internal virtual host's name. It has to be set to the name under which the service is accessed. In this case - `mgmt-web-svc.example.com`
* `linyio/mgmt-web-svc`: specifies the docker image (`linyio/mgmt-web-svc`) and the image name (`mgmt-web-svc`). If not tag specified, as abovem, then the `latest` will be considered.

A nginx configuration example:
```nginx
server {
        listen 80; #for http redirect to https
        server_name mgmt-web-svc.example.com;
        return 301 https://$host$request_uri; #return a 301 http status code - permanently moved
}

server {
        listen 443 ssl;
        server_name mgmt-web-svc.example.com;
        server_tokens off;

        ssl_certificate     /etc/letsencrypt/live/liny.io/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/liny.io/privkey.pem;

        # disabled client verification (because Mattermost Android app don't support it) and enforced 2FA.
        ssl_verify_client on;
        ssl_client_certificate /etc/nginx/certs/liny-ca.crt; #the client certificate CA

        ssl_session_timeout 5m;

        ssl_protocols TLSv1.1 TLSv1.2;
        ssl_ciphers "HIGH:!aNULL:!MD5 or HIGH:!aNULL:!MD5:!3DES";
        ssl_prefer_server_ciphers on;
        ssl_session_cache shared:SSL:10m;

        chunked_transfer_encoding on;

        location  / {
            uwsgi_pass unix:///var/run/nginx/uwsgi.sock;
            #uwsgi_pass 127.0.0.1:8084;
            include uwsgi_params;
        }
}
```

#### HTTP - standalone but insecure

**WARNING:** This mode is highly insecure. It should be used only in development or trusted network environments or with
a ssl termination in front (such as nginx).

To launch the docker container as a standalone (insecure) http server run:
```
docker container run -d -p 8084:8084 -v mgmt-web-svc:/var/run/MgmtWebSvc/Db --name mgmt-web-svc 
-e USER_IDS=486ce768-1d41-4bcf-b49c-9a770e185994  -e UWSGI_HTTP=":8084" -e SERVER_NAME="mgmt-web-svc.example.com" 
linyio/mgmt-web-svc
```
with the following explanations for the newly introduced options:
* `-p 8084:8084`: tcp port mapping between host and container, where the api http service will be available
* `-e USER_IDS=486ce768-1d41-4bcf-b49c-9a770e185994`: the user to be accepted in JWTs
* `-e UWSGI_HTTP=":8084"`: instructs the container to expose the service as http (as oposed to the uWSGI as in the 
        previous example) using TCP/IP protocol and listens on port 8084. Note: it must to closely match with the `-p 8084:8084` option

Note: the options present also in the previous examples share the same explanations.

### Reference
The docker container can be customized using a set of environment variables (`-e` options given when running a docker container). There are two environment variables categories:
* container's specific: which refer to the container itself
* uWSGI specific: are environment variables used to customise the uWSGI server
#### Container specific environment variables
* `VERSION_EXTRA`: specifies a string used to append to the api version in the swagger documentation page. It rarely need to be touched and it defaults to the docker container build timestamp
* `DIR`: the directory within container where the database will reside. It defaults to `/var/run/MgmtWebSvc/Db`
* `DB_PATH`: the db path. It defaults to `${DB_DIR}/db.sqlite`
* `DB_URL`: the db url schema. It defaults to `sqlite:///$DB_PATH`
* `SERVER_NAME`: the container's internal "virtual host's name". It has to be set to the name under which the api http service is accessed. Example: `mgmt-web-svc.example.com`
* `DOC`: if set to any value other than `On`, `1` or `True` it disables the swagger documentation page (ex. https://mgmt-web-svc.example.com/apidocs/). If not set then the `setting.SWAGGER_DOC` (see `settings.py`) option is used, which currently is set to `True`
* `DOC_PREFIX`: the prefix under which the api's swagger documentation is accessible. If not set then the internal `settings.SWAGGER_DOC_PREFIX`  (see `settings.py`) option is used, which currently is set to `"/apidocs/"`

#### uWSGI specific environment variables
* `UWSGI_STATS`: if set, enables the uWSGI statistics. It can be in the form of `[<host>]:<tcp_port>` for accessing it through tcp/ip or `<unix_socket_path>` for unix sockets. The setting has to make through the container to the host to be actually accessible. For more info see the [uWSGI stats documentation page](https://uwsgi-docs.readthedocs.io/en/latest/StatsServer.html)
* `UWSGI_HTTPS`: if set, exposes the api through the slower https protocol, insted of the high performance uWSGI protocol. It can be in the form of `[<host>]:<tcp_port,<cert>,<key>`. The setting has to make through the container to the host to be actually accessible. For more info see the [uWSGI https documentation page](https://uwsgi-docs.readthedocs.io/en/latest/HTTPS.html)
* `UWSGI_HTTP`: if set, exposes the api through the slower http protocol, insted of the high performance uWSGI protocol. It can be in the form of `[<host>]:<tcp_port>` for accessing it through tcp/ip or `<unix_socket_path>` for unix sockets. The setting has to make through the container to the host to be actually accessible. For more info see the [uWSGI http documentation page](https://uwsgi-docs.readthedocs.io/en/latest/HTTP.html)
* `UWSGI_SOCKET`: sets the uWSGI socket. By default the `${DB_DIR}/MgmtWebSvc.sock` socket is used. Make sure the path is accessible by the host through docker volumes. It can be in the form of `[<host>]:<tcp_port>` for accessing it through tcp/ip or `<unix_socket_path>` for unix sockets. The setting has to make through the container to the host to be actually accessible. For more info see the [uWSGI socker documentation page](https://uwsgi-docs.readthedocs.io/en/latest/WSGIquickstart.html#putting-behind-a-full-webserver)
* `UWSGI_UID`: the user under which the wsgi server runs within docker container. The user has to at least access the db and the db directory has to be writable by the specified user. Default user: `nobody`
* `UWSGI_CHOWN_SOCKET`: sets the uWSGI unix sockets ownership. It's useful for setting uWSGI socket permissions so that processes which run on host may be able to access it (nginx for example). Default: `${UWSGI_UID}`. Example: `-e UWSGI_CHOWN_SOCKET="$(id -u nginx):$(id -g nginx)"`
* `UWSGI_WORKERS`: the uWSGI maximum number of workers. It defaults to 8 workers. The workers frmework uses cheaper subsystem for adaprive workers spawning with the spare algorithm with one initial worker. For more info see [The uWSGI cheaper subsystem – adaptive process spawning](https://uwsgi-docs.readthedocs.io/en/latest/Cheaper.html#the-uwsgi-cheaper-subsystem-adaptive-process-spawning)
* any other uWSGI environment variable which overrides an uWSGI option as decribe at [uWSGI environme variables configuration](https://uwsgi-docs.readthedocs.io/en/latest/Configuration.html#environment-variables). The uWSGI complete configuration options reference can be accessed at [uWSGI Options](https://uwsgi-docs.readthedocs.io/en/latest/Options.html)

## 2. Python virtual environment

For local development/debugging, the best practice dictates to install all the needed packages into a virtual environment so that the system wide python packages repository wouldn't be clutered. To create such a virtualenv run: 
```
virtualenv -p $(which python3) PyVenv && source PyVenv/bin/activate && pip install -r requirements.txt
```

To exit from the Python virtual environment just create run: 
```
deactivate
```
