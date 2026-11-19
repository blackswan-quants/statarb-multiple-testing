cmake_minimum_required(VERSION 3.20)
project(statarb_engine LANGUAGES CXX)

# C++17, strictly: no compiler-specific extensions
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# --- Dependencies: downloaded at configure time, pinned versions -----------
include(FetchContent)

# Eigen 3.4.0 (header-only linear algebra).
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