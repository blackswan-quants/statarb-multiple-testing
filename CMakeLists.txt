cmake_minimum_required(VERSION 3.20)
project(statarb_engine LANGUAGES CXX)

# C++17, strictly: no compiler-specific extensions
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# --- Dependencies: downloaded at configure time, pinned versions -----------
include(FetchContent)

# Eigen 3.4.1 (header-only linear algebra).
# SOURCE_SUBDIR points to a folder that does not exist, so CMake only
# downloads the headers and does not build Eigen's own tests and docs.
FetchContent_Declare(
  eigen
  GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
  GIT_TAG        3.4.1
  GIT_SHALLOW    TRUE
  SOURCE_SUBDIR  do-not-build
)
FetchContent_MakeAvailable(eigen)

add_library(eigen_headers INTERFACE)
target_include_directories(eigen_headers SYSTEM INTERFACE ${eigen_SOURCE_DIR})
add_library(Eigen3::Eigen ALIAS eigen_headers)

# Catch2 v3 (unit testing framework)
FetchContent_Declare(
  Catch2
  GIT_REPOSITORY https://github.com/catchorg/Catch2.git
  GIT_TAG        v3.7.1
  GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(Catch2)

# --- Engine library ---------------------------------------------------------
add_library(engine engine/src/ols.cpp)
target_include_directories(engine PUBLIC engine/include)
target_link_libraries(engine PUBLIC Eigen3::Eigen)

# Strict warnings on our own code
if(MSVC)
  target_compile_options(engine PRIVATE /W4)
else()
  target_compile_options(engine PRIVATE -Wall -Wextra -Wpedantic)
endif()

# --- Tests ------------------------------------------------------------------
enable_testing()

add_executable(engine_tests engine/tests/test_ols.cpp)
target_link_libraries(engine_tests PRIVATE engine Catch2::Catch2WithMain)

# Register every TEST_CASE with CTest
list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
include(Catch)
catch_discover_tests(engine_tests)