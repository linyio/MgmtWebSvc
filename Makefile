.PHONY: build push build-and-push build-public push-public build-and-push-public deploy deploy-with-shell deploy-vers-check rm-docker

makeFileDir := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

ifndef DOCKER_REGISTRY
	DOCKER_REGISTRY := docker-registry.liny.io
endif
ifndef DOCKER_CONTAINER_NAME
	DOCKER_CONTAINER_NAME := linyio/mgmt-web-svc
endif
ifndef DOCKER_IMAGE_TAG
	DOCKER_IMAGE_TAG := latest
endif
ifndef DOCKER_PATH
	DOCKER_PATH := $(makeFileDir)
endif

DOCKER_IMAGE_NAME = $(DOCKER_REGISTRY)/$(DOCKER_CONTAINER_NAME):$(DOCKER_IMAGE_TAG)
DOCKER_IMAGE_PUBLIC_NAME = $(DOCKER_CONTAINER_NAME):$(DOCKER_IMAGE_TAG)
#dokerfile relative path to the script dir
DOKERFILE_DEFAULT_REL_DIR := ..
DEFAULT_VERSION_EXTRA := " - $(date '+%Y-%m-%d %H:%M:%S')"
ifndef PORT
	PORT := 8083
endif

build:
	docker build --pull -t $(DOCKER_IMAGE_NAME) --build-arg VERSION_EXTRA="$(VERSION_EXTRA:-$(DEFAULT_VERSION_EXTRA))"\
    	$(DOCKER_PATH)

build-public:
	docker build --pull -t $(DOCKER_IMAGE_PUBLIC_NAME)\
		--build-arg VERSION_EXTRA="$(VERSION_EXTRA:-$(DEFAULT_VERSION_EXTRA))" $(DOCKER_PATH)

build-and-push: build push

push:
	docker push $(DOCKER_IMAGE_NAME)

push-public:
	docker push $(DOCKER_IMAGE_PUBLIC_NAME)

build-and-push-public: build-public push-public

rm-docker:
	-docker container stop liny-mgmt-web-svc-$(PORT)
	-docker container rm liny-mgmt-web-svc-$(PORT)

deploy-vers-check:
	@if [ -z "$$HOST" ]; then\
 		echo "The HOST environment variable must be set. It's needed for determining the server name"; exit 1;\
 	fi
	@if [ -z "$$USER_IDS" ]; then\
 		echo "The USER_IDS environment variable must be set. It's needed for securing the service access, via JWT. \
If unsure, take it from the Liny's web app - management web service deployment step by step guide";\
 		exit 1;\
 	fi

#should be ran on the machine with docker daemon. Useful for development/debugging
deploy: deploy-vers-check rm-docker
	docker container run -d -p $(PORT):$(PORT) -e "USER_IDS=$(USER_IDS)" -e "HOST=$(HOST)" -e "PORT=$(PORT)"\
 --hostname $(HOST) -v LinyMgmtWebSvc-HostCerts:/var/run/MgmtWebSvc/Certs\
 -v LinyMgmtWebSvc-Db-$(HOST)-$(PORT):/var/run/MgmtWebSvc/Db --name liny-mgmt-web-svc-$(PORT)\
 $(DOCKER_IMAGE_NAME)

#deploy the container but drop it to a shell
deploy-with-shell: deploy-vers-check rm-docker
	docker container run -p $(PORT):$(PORT) -e "USER_IDS=$(USER_IDS)" -e "HOST=$(HOST)" -e "PORT=$(PORT)"\
 --hostname $(HOST)  -v LinyMgmtWebSvc-HostCerts:/var/run/MgmtWebSvc/Certs\
 -v LinyMgmtWebSvc-Db-$(HOST)-$(PORT):/var/run/MgmtWebSvc/Db --name liny-mgmt-web-svc-$(PORT) --rm -it\
 $(DOCKER_IMAGE_NAME) sh
