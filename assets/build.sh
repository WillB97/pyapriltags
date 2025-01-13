#!/bin/bash -e
# repository is mounted at /apriltag, build files are under /builds
# built shared libraries are stored under /dist, wheels are stored in /out

# TODO quit if /apriltag doesn't exist

mkdir -p \
    /{builds,dist}/{win64,win32,mac_aarch64,mac_amd64,linux_amd64,linux_aarch64,linux_armhf}
mkdir -p out

COMMON_CMAKE_ARGS="-DBUILD_SHARED_LIBS=ON -DCMAKE_C_COMPILER_WORKS=1 -DCMAKE_CXX_COMPILER_WORKS=1 -DCMAKE_BUILD_TYPE=Release -DBUILD_PYTHON_WRAPPER=OFF -DBUILD_EXAMPLES=OFF"

do_compile() {
    printf "\n>>> BUILDING APRILTAG for $1\n"
    cd /builds/$1 || return
    cmake $4 \
        -DCMAKE_C_COMPILER=$2 -DCMAKE_CXX_COMPILER=$3 \
        $COMMON_CMAKE_ARGS /apriltag/apriltags || return
    cmake --build . --config Release || return
    cp -L libapriltag.* /dist/$1
}

get_glibc_version() {
    # $1 is the compiler
    libc_link=$($1 -print-file-name=libc.so.6)
    readlink -f $libc_link | sed -E 's/.*libc-([0-9]+)\.([0-9]+)\.so/\1_\2/'
}

build_wheel() {
    cp /dist/$1/$2 pyapriltags/ || return
    pip wheel --wheel-dir /out --no-deps --build-option=--plat-name=$3 .
    rm -rf build/lib  # remove cached shared libraries
    rm pyapriltags/$2
}

do_compile win64 x86_64-w64-mingw32-gcc x86_64-w64-mingw32-g++ "-DCMAKE_SYSTEM_NAME=Windows"
do_compile win32 i686-w64-mingw32-gcc i686-w64-mingw32-g++ "-DCMAKE_SYSTEM_NAME=Windows"
do_compile mac_aarch64 oa64-clang oa64-clang++ "-DCMAKE_SYSTEM_NAME=Darwin -DCMAKE_OSX_ARCHITECTURES=arm64"
do_compile mac_amd64 o64-clang o64-clang++ "-DCMAKE_SYSTEM_NAME=Darwin -DCMAKE_OSX_ARCHITECTURES=x86_64"
ARCH="$(uname -m)"
if [[ "$ARCH" == "x86_64" ]]; then
    do_compile linux_amd64 gcc g++ "-DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=x86_64"
    do_compile linux_aarch64 aarch64-linux-gnu-gcc aarch64-linux-gnu-g++ "-DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=arm"
else
    do_compile linux_aarch64 gcc g++ "-DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=arm"
    do_compile linux_amd64 x86_64-linux-gnu-gcc x86_64-linux-gnu-g++ "-DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=x86_64"
fi
do_compile linux_armhf arm-linux-gnueabihf-gcc arm-linux-gnueabihf-g++ "-DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=arm"

# build wheels
cd /apriltag
if [[ "$ARCH" == "x86_64" ]]; then
    build_wheel linux_aarch64 libapriltag.so manylinux_$(get_glibc_version aarch64-linux-gnu-gcc)_aarch64
    build_wheel linux_amd64 libapriltag.so manylinux_$(get_glibc_version gcc)_x86_64
else
    build_wheel linux_aarch64 libapriltag.so manylinux_$(get_glibc_version gcc)_aarch64
    build_wheel linux_amd64 libapriltag.so manylinux_$(get_glibc_version x86_64-linux-gnu-gcc)_x86_64
fi
build_wheel linux_armhf libapriltag.so manylinux_$(get_glibc_version arm-linux-gnueabihf-gcc)_armv7l
build_wheel win64 libapriltag.dll win-amd64
build_wheel win32 libapriltag.dll win32
build_wheel mac_aarch64 libapriltag.dylib macosx_11_0_arm64
build_wheel mac_amd64 libapriltag.dylib macosx_11_0_x86_64
