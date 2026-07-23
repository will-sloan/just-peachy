set -ex

title () {
	set +x
	title_len=$(printf "$1" | wc -c)
	echo
	echo $1
	printf "=%.0s" $(seq $title_len)
	printf "\n"
	echo
	set -x
}

ROOT_DIR=$(pwd)

# change to directory relative to this script
cd $(dirname -- $0)/../..

title "Installing xshf"
cmake -S modules/xshf \
	-B build/xshf \
	--toolchain=xmos_cmake_toolchain/xs3a.cmake \
	-GNinja \
	-DCMAKE_INSTALL_PREFIX=build/install
cmake --build build/xshf --target install

title "Configure unit tests"
# note, running from ROOT_DIR as unit test dependencies are not included in the release
cmake --preset=default

title "Building tests"
cmake --build --preset default -j$(nproc) -t all_tests

# Runs all tests specified with `add_test` in the CMakeLists.
# runs tests in parallel
title "Running ctest"
ctest --output-junit ${ROOT_DIR}/ctest_results.xml \
	--preset=default \
	-j$(nproc)
