.PHONY: docker-build docker-run docker-clean build run clean connect health

export USER
PLUGIN_NAME="ansible-plugin-clicap"
PLUGIN_NAME_EGG := $(subst -,_,$(PLUGIN_NAME))
PLUGIN_VER="0.2"
DOCKER_IMAGE_NAME="greenpau/ansible2"
DOCKER_CONTAINER_NAME="ansible2"
DOCKER_CONTAINER_SHELL="/bin/sh"
DOCKER_BINARY='docker'
ifneq "${USER}" "root"
  DOCKER_BINARY='sudo docker'
endif

all:
	@echo 'the only available options are: build, run, clean, and status' || false

build:
	@eval ${DOCKER_BINARY} build -t ${DOCKER_IMAGE_NAME} .

run:
	@eval ${DOCKER_BINARY} run -d -t --name=${DOCKER_CONTAINER_NAME} ${DOCKER_IMAGE_NAME} && \
	echo "'"${DOCKER_IMAGE_NAME}"' container was started successfully!" || \
	(echo "failed to start '"${DOCKER_IMAGE_NAME}"'" && \
	eval ${DOCKER_BINARY} inspect --format='ExitCode: {{.State.ExitCode}}' ${DOCKER_CONTAINER_NAME} && \
	eval ${DOCKER_BINARY} inspect --format='Log file: {{.LogPath}}' ${DOCKER_CONTAINER_NAME})

clean:
	@eval ${DOCKER_BINARY} stop ${DOCKER_CONTAINER_NAME} || true
	@eval ${DOCKER_BINARY} rm ${DOCKER_CONTAINER_NAME} || true

status:
	@eval ${DOCKER_BINARY} ps --all | egrep ${DOCKER_CONTAINER_NAME}
	@eval ${DOCKER_BINARY} inspect --format=\"ExitCode: {{.State.ExitCode}}\" ${DOCKER_CONTAINER_NAME} || echo "no such container" && false
	@eval ${DOCKER_BINARY} inspect --format=\"Log file: {{.LogPath}}\" ${DOCKER_CONTAINER_NAME}
	@eval ${DOCKER_BINARY} exec -i -t ${DOCKER_CONTAINER_NAME} hostname

connect:
	@echo ${DOCKER_BINARY} exec -i -t ${DOCKER_CONTAINER_NAME} ${DOCKER_CONTAINER_SHELL}

package:
	@sed -i 's/pkg_ver =.*/pkg_ver = ${PLUGIN_VER};/' setup.py
	@sed -i 's/-[0-9]\.[0-9].tar.gz/-${PLUGIN_VER}.tar.gz/;s/"//g;s/ENTRYPOINT.*/ENTRYPOINT \["\/bin\/sh"\]/;' Dockerfile
	@pandoc --from=markdown --to=rst --output=${PLUGIN_NAME}/README.rst README.md
	@rm -rf dist/
	@python setup.py sdist
	@rm -rf ${PLUGIN_NAME_EGG}.egg-info *.egg build/
	@find . -name \*.pyc -delete
	@tar -tvf dist/${PLUGIN_NAME}-${PLUGIN_VER}.tar.gz

#health:
#	DOCKER_CONTAINER_EXITED=$(docker ps -a | egrep -e \"Exited \\([0-9]+\\) [0-9]+ days ago\" | cut -d\" \" -f1)
#	@echo ${DOCKER_CONTAINER_EXITED}
