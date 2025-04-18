ROOT=$(dir $(abspath $(firstword $(MAKEFILE_LIST))))

.PHONY: build upload clean release-all

all: docker-build build

build:
	# create wheel destination directory
	mkdir -p ${ROOT}/dist
	# build wheel
	docker run \
		--rm -t \
		-v ${ROOT}:/apriltag \
		-v ${ROOT}/dist:/out \
		pyapriltags:wheel-python3

docker-build:
	# create build environment
	docker build \
		-t pyapriltags:wheel-python3 \
		${ROOT}

upload:
	twine upload ${ROOT}/dist/*

clean:
	rm -rf ${ROOT}/dist/*

release-all:
	# build wheels
	make build
	# push wheels
	make upload
