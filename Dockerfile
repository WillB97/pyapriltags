# syntax=docker/dockerfile:1

# get OSX SDK
ARG OSXCROSS_VERSION=13.1-r0
FROM crazymax/osxcross:${OSXCROSS_VERSION}-ubuntu AS osxcross

FROM ubuntu:20.04
ENV PATH="/osxcross/bin:$PATH"
ENV LD_LIBRARY_PATH="/osxcross/lib"
COPY --from=osxcross /osxcross /osxcross

ARG DEBIAN_FRONTEND=noninteractive
# install most the compilers needed for all targets
RUN apt-get update && apt-get install -y clang lld libc6-dev \
    cmake make libtool gcc g++ \
    gcc-mingw-w64-x86-64 g++-mingw-w64-x86-64 \
    gcc-mingw-w64-i686 g++-mingw-w64-i686 \
    gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf \
    python3-pip

# install the remaining compiler dependent on the container architecture
RUN if [ "$(uname -m)" = "x86_64" ]; then \
        apt-get install -y gcc-aarch64-linux-gnu g++-aarch64-linux-gnu; \
    else \
        apt-get install -y gcc-x86-64-linux-gnu g++-x86-64-linux-gnu; \
    fi

# install python libraries
RUN pip install "numpy==1.24.4" uv

# support from win7 in mingw
ENV CFLAGS="-DWINVER=0x0600 -D_WIN32_WINNT=0x0600"

# install building script
COPY ./assets/build.sh /build.sh

# define command
CMD /build.sh
