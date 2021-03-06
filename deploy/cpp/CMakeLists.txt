cmake_minimum_required(VERSION 3.0)
project(PaddleX CXX C)

option(WITH_MKL        "Compile demo with MKL/OpenBlas support,defaultuseMKL."          ON)
option(WITH_GPU        "Compile demo with GPU/CPU, default use CPU."                    ON)
if (NOT WIN32)
    option(WITH_STATIC_LIB "Compile demo with static/shared library, default use static."   OFF)
else()
    option(WITH_STATIC_LIB "Compile demo with static/shared library, default use static."   ON)
endif()
option(WITH_TENSORRT "Compile demo with TensorRT."   OFF)
option(WITH_ENCRYPTION "Compile demo with encryption tool."   OFF)

SET(TENSORRT_DIR "" CACHE PATH "Location of libraries")
SET(PADDLE_DIR "" CACHE PATH "Location of libraries")
SET(OPENCV_DIR "" CACHE PATH "Location of libraries")
SET(ENCRYPTION_DIR "" CACHE PATH "Location of libraries")
SET(CUDA_LIB "" CACHE PATH "Location of libraries")

if (NOT WIN32)
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/demo)
else()
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/paddlex_inference)
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/paddlex_inference)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/paddlex_inference)
endif()

if (NOT WIN32)
    SET(YAML_BUILD_TYPE ON CACHE BOOL "yaml build shared library.")
else()
    SET(YAML_BUILD_TYPE OFF CACHE BOOL "yaml build shared library.")
endif()
include(cmake/yaml-cpp.cmake)

include_directories("${CMAKE_SOURCE_DIR}/")
include_directories("${CMAKE_CURRENT_BINARY_DIR}/ext/yaml-cpp/src/ext-yaml-cpp/include")
link_directories("${CMAKE_CURRENT_BINARY_DIR}/ext/yaml-cpp/lib")

macro(safe_set_static_flag)
    foreach(flag_var
        CMAKE_CXX_FLAGS CMAKE_CXX_FLAGS_DEBUG CMAKE_CXX_FLAGS_RELEASE
        CMAKE_CXX_FLAGS_MINSIZEREL CMAKE_CXX_FLAGS_RELWITHDEBINFO)
      if(${flag_var} MATCHES "/MD")
        string(REGEX REPLACE "/MD" "/MT" ${flag_var} "${${flag_var}}")
      endif(${flag_var} MATCHES "/MD")
    endforeach(flag_var)
endmacro()


if (WITH_ENCRYPTION)
  if (NOT (${CMAKE_SYSTEM_PROCESSOR} STREQUAL "aarch64"))
    add_definitions( -DWITH_ENCRYPTION=${WITH_ENCRYPTION})
  endif()
endif()

if (WITH_MKL)
    ADD_DEFINITIONS(-DUSE_MKL)
endif()

if (NOT DEFINED PADDLE_DIR OR ${PADDLE_DIR} STREQUAL "")
    message(FATAL_ERROR "please set PADDLE_DIR with -DPADDLE_DIR=/path/paddle_influence_dir")
endif()

if (NOT (${CMAKE_SYSTEM_PROCESSOR} STREQUAL "aarch64"))
  if (NOT DEFINED OPENCV_DIR OR ${OPENCV_DIR} STREQUAL "")
    message(FATAL_ERROR "please set OPENCV_DIR with -DOPENCV_DIR=/path/opencv")
  endif()
endif()

include_directories("${CMAKE_SOURCE_DIR}/")
include_directories("${PADDLE_DIR}/")
include_directories("${PADDLE_DIR}/third_party/install/protobuf/include")
include_directories("${PADDLE_DIR}/third_party/install/glog/include")
include_directories("${PADDLE_DIR}/third_party/install/gflags/include")
include_directories("${PADDLE_DIR}/third_party/install/xxhash/include")
if (EXISTS "${PADDLE_DIR}/third_party/install/snappy/include")
    include_directories("${PADDLE_DIR}/third_party/install/snappy/include")
endif()
if(EXISTS "${PADDLE_DIR}/third_party/install/snappystream/include")
    include_directories("${PADDLE_DIR}/third_party/install/snappystream/include")
endif()
# zlib does not exist in 1.8.1
if (EXISTS "${PADDLE_DIR}/third_party/install/zlib/include")
    include_directories("${PADDLE_DIR}/third_party/install/zlib/include")
endif()

include_directories("${PADDLE_DIR}/third_party/boost")
include_directories("${PADDLE_DIR}/third_party/eigen3")

if (EXISTS "${PADDLE_DIR}/third_party/install/snappy/lib")
    link_directories("${PADDLE_DIR}/third_party/install/snappy/lib")
endif()
if(EXISTS "${PADDLE_DIR}/third_party/install/snappystream/lib")
    link_directories("${PADDLE_DIR}/third_party/install/snappystream/lib")
endif()

if (EXISTS "${PADDLE_DIR}/third_party/install/zlib/lib")
    link_directories("${PADDLE_DIR}/third_party/install/zlib/lib")
endif()

link_directories("${PADDLE_DIR}/third_party/install/protobuf/lib")
link_directories("${PADDLE_DIR}/third_party/install/glog/lib")
link_directories("${PADDLE_DIR}/third_party/install/gflags/lib")
link_directories("${PADDLE_DIR}/third_party/install/xxhash/lib")
link_directories("${PADDLE_DIR}/paddle/lib/")
link_directories("${CMAKE_CURRENT_BINARY_DIR}")

if (WIN32)
  include_directories("${PADDLE_DIR}/paddle/fluid/inference")
  include_directories("${PADDLE_DIR}/paddle/include")
  link_directories("${PADDLE_DIR}/paddle/fluid/inference")
  find_package(OpenCV REQUIRED PATHS ${OPENCV_DIR}/build/ NO_DEFAULT_PATH)
  unset(OpenCV_DIR CACHE)
else ()
  if (${CMAKE_SYSTEM_PROCESSOR} STREQUAL "aarch64") # x86_64 aarch64
    set(OpenCV_INCLUDE_DIRS "/usr/include/opencv4")
    file(GLOB OpenCV_LIBS /usr/lib/aarch64-linux-gnu/libopencv_*${CMAKE_SHARED_LIBRARY_SUFFIX})
    message("OpenCV libs: ${OpenCV_LIBS}")
  else()
    find_package(OpenCV REQUIRED PATHS ${OPENCV_DIR}/share/OpenCV NO_DEFAULT_PATH)
  endif()
  include_directories("${PADDLE_DIR}/paddle/include")
  link_directories("${PADDLE_DIR}/paddle/lib")
endif ()

include_directories(${OpenCV_INCLUDE_DIRS})

if (WIN32)
    add_definitions("/DGOOGLE_GLOG_DLL_DECL=")
    find_package(OpenMP REQUIRED)
    if (OPENMP_FOUND)
        message("OPENMP FOUND")
        set(CMAKE_C_FLAGS_DEBUG   "${CMAKE_C_FLAGS_DEBUG} ${OpenMP_C_FLAGS}")
        set(CMAKE_C_FLAGS_RELEASE  "${CMAKE_C_FLAGS_RELEASE} ${OpenMP_C_FLAGS}")
        set(CMAKE_CXX_FLAGS_DEBUG  "${CMAKE_CXX_FLAGS_DEBUG} ${OpenMP_CXX_FLAGS}")
        set(CMAKE_CXX_FLAGS_RELEASE   "${CMAKE_CXX_FLAGS_RELEASE} ${OpenMP_CXX_FLAGS}")
    endif()
    set(CMAKE_C_FLAGS_DEBUG   "${CMAKE_C_FLAGS_DEBUG} /bigobj /MTd")
    set(CMAKE_C_FLAGS_RELEASE  "${CMAKE_C_FLAGS_RELEASE} /bigobj /MT")
    set(CMAKE_CXX_FLAGS_DEBUG  "${CMAKE_CXX_FLAGS_DEBUG} /bigobj /MTd")
    set(CMAKE_CXX_FLAGS_RELEASE   "${CMAKE_CXX_FLAGS_RELEASE} /bigobj /MT")
    if (WITH_STATIC_LIB)
        safe_set_static_flag()
        add_definitions(-DSTATIC_LIB)
    endif()
else()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -g -o2 -fopenmp -std=c++11")
    set(CMAKE_STATIC_LIBRARY_PREFIX "")
endif()

if (WITH_GPU)
    if (NOT DEFINED CUDA_LIB OR ${CUDA_LIB} STREQUAL "")
        message(FATAL_ERROR "please set CUDA_LIB with -DCUDA_LIB=/path/cuda/lib64")
    endif()
    if (NOT WIN32)
        if (NOT DEFINED CUDNN_LIB)
            message(FATAL_ERROR "please set CUDNN_LIB with -DCUDNN_LIB=/path/cudnn/")
        endif()
    endif(NOT WIN32)
endif()


if (NOT WIN32)
  if (WITH_TENSORRT AND WITH_GPU)
      if (${CMAKE_SYSTEM_PROCESSOR} STREQUAL "aarch64") # x86_64 aarch64
          include_directories("/usr/include/aarch64-linux-gnu")
	  link_directories("/usr/lib/aarch64-linux-gnu")
      else()
          include_directories("${TENSORRT_DIR}/include")
          link_directories("${TENSORRT_DIR}/lib")
      endif()
  endif()
endif(NOT WIN32)

if (NOT WIN32)
    set(NGRAPH_PATH "${PADDLE_DIR}/third_party/install/ngraph")
    if(EXISTS ${NGRAPH_PATH})
        include(GNUInstallDirs)
        include_directories("${NGRAPH_PATH}/include")
        link_directories("${NGRAPH_PATH}/${CMAKE_INSTALL_LIBDIR}")
        set(NGRAPH_LIB ${NGRAPH_PATH}/${CMAKE_INSTALL_LIBDIR}/libngraph${CMAKE_SHARED_LIBRARY_SUFFIX})
    endif()
endif()

if(WITH_MKL)
  include_directories("${PADDLE_DIR}/third_party/install/mklml/include")
  if (WIN32)
    set(MATH_LIB ${PADDLE_DIR}/third_party/install/mklml/lib/mklml.lib
            ${PADDLE_DIR}/third_party/install/mklml/lib/libiomp5md.lib)
  else ()
    set(MATH_LIB ${PADDLE_DIR}/third_party/install/mklml/lib/libmklml_intel${CMAKE_SHARED_LIBRARY_SUFFIX}
            ${PADDLE_DIR}/third_party/install/mklml/lib/libiomp5${CMAKE_SHARED_LIBRARY_SUFFIX})
    execute_process(COMMAND cp -r ${PADDLE_DIR}/third_party/install/mklml/lib/libmklml_intel${CMAKE_SHARED_LIBRARY_SUFFIX} /usr/lib)
  endif ()
  set(MKLDNN_PATH "${PADDLE_DIR}/third_party/install/mkldnn")
  if(EXISTS ${MKLDNN_PATH})
    include_directories("${MKLDNN_PATH}/include")
    if (WIN32)
      set(MKLDNN_LIB ${MKLDNN_PATH}/lib/mkldnn.lib)
    else ()
      set(MKLDNN_LIB ${MKLDNN_PATH}/lib/libmkldnn.so.0)
    endif ()
  endif()
else()
  set(MATH_LIB ${PADDLE_DIR}/third_party/install/openblas/lib/libopenblas${CMAKE_STATIC_LIBRARY_SUFFIX})
endif()

if (WIN32)
    if(EXISTS "${PADDLE_DIR}/paddle/fluid/inference/libpaddle_fluid${CMAKE_STATIC_LIBRARY_SUFFIX}")
        set(DEPS
            ${PADDLE_DIR}/paddle/fluid/inference/libpaddle_fluid${CMAKE_STATIC_LIBRARY_SUFFIX})
    else()
        set(DEPS
            ${PADDLE_DIR}/paddle/lib/libpaddle_fluid${CMAKE_STATIC_LIBRARY_SUFFIX})
    endif()
endif()

if(WITH_STATIC_LIB)
    set(DEPS
        ${PADDLE_DIR}/paddle/lib/libpaddle_fluid${CMAKE_STATIC_LIBRARY_SUFFIX})
else()
    if (NOT WIN32)
      set(DEPS
          ${PADDLE_DIR}/paddle/lib/libpaddle_fluid${CMAKE_SHARED_LIBRARY_SUFFIX})
    else()
      set(DEPS
          ${PADDLE_DIR}/paddle/lib/paddle_fluid${CMAKE_SHARED_LIBRARY_SUFFIX})
    endif()
endif()

if (NOT WIN32)
    set(DEPS ${DEPS}
        ${MATH_LIB} ${MKLDNN_LIB}
        glog gflags protobuf xxhash yaml-cpp
        )
    if(EXISTS "${PADDLE_DIR}/third_party/install/snappystream/lib")
        set(DEPS ${DEPS} snappystream)
    endif()
    if (EXISTS "${PADDLE_DIR}/third_party/install/snappy/lib")
        set(DEPS ${DEPS} snappy)
    endif()
else()
    set(DEPS ${DEPS}
        ${MATH_LIB} ${MKLDNN_LIB}
        glog gflags_static libprotobuf xxhash libyaml-cppmt)

    if (EXISTS "${PADDLE_DIR}/third_party/install/zlib/lib")
      set(DEPS ${DEPS} zlibstatic)
    endif()
    set(DEPS ${DEPS} libcmt shlwapi)
    if (EXISTS "${PADDLE_DIR}/third_party/install/snappy/lib")
        set(DEPS ${DEPS} snappy)
    endif()
    if (EXISTS "${PADDLE_DIR}/third_party/install/snappystream/lib")
        set(DEPS ${DEPS} snappystream)
    endif()
endif(NOT WIN32)

if(WITH_GPU)
  if(NOT WIN32)
    if (WITH_TENSORRT)
      if (${CMAKE_SYSTEM_PROCESSOR} STREQUAL "aarch64") # x86_64 aarch64
	set(DEPS ${DEPS} /usr/lib/aarch64-linux-gnu/libnvinfer${CMAKE_SHARED_LIBRARY_SUFFIX})
        set(DEPS ${DEPS} /usr/lib/aarch64-linux-gnu/libnvinfer_plugin${CMAKE_SHARED_LIBRARY_SUFFIX})
      else()
	set(DEPS ${DEPS} ${TENSORRT_DIR}/lib/libnvinfer${CMAKE_SHARED_LIBRARY_SUFFIX})
        set(DEPS ${DEPS} ${TENSORRT_DIR}/lib/libnvinfer_plugin${CMAKE_SHARED_LIBRARY_SUFFIX})
      endif()
    endif()
    set(DEPS ${DEPS} ${CUDA_LIB}/libcudart${CMAKE_SHARED_LIBRARY_SUFFIX})
    set(DEPS ${DEPS} ${CUDNN_LIB}/libcudnn${CMAKE_SHARED_LIBRARY_SUFFIX})
  else()
    set(DEPS ${DEPS} ${CUDA_LIB}/cudart${CMAKE_STATIC_LIBRARY_SUFFIX} )
    set(DEPS ${DEPS} ${CUDA_LIB}/cublas${CMAKE_STATIC_LIBRARY_SUFFIX} )
    set(DEPS ${DEPS} ${CUDA_LIB}/cudnn${CMAKE_STATIC_LIBRARY_SUFFIX})
  endif()
endif()

if(WITH_ENCRYPTION)
  if(NOT WIN32)
    if (NOT (${CMAKE_SYSTEM_PROCESSOR} STREQUAL "aarch64"))
      include_directories("${ENCRYPTION_DIR}/include")
      link_directories("${ENCRYPTION_DIR}/lib")
      set(DEPS ${DEPS} ${ENCRYPTION_DIR}/lib/libpmodel-decrypt${CMAKE_SHARED_LIBRARY_SUFFIX})
    endif()
  else()
      include_directories("${ENCRYPTION_DIR}/include")
      link_directories("${ENCRYPTION_DIR}/lib")
      set(DEPS ${DEPS} ${ENCRYPTION_DIR}/lib/pmodel-decrypt${CMAKE_STATIC_LIBRARY_SUFFIX})
  endif()
endif()

if (NOT WIN32)
    set(EXTERNAL_LIB "-ldl -lrt -lgomp -lz -lm -lpthread")
    set(DEPS ${DEPS} ${EXTERNAL_LIB})
endif()

set(DEPS ${DEPS} ${OpenCV_LIBS})

add_library(paddlex_inference SHARED src/visualize src/transforms.cpp src/paddlex.cpp)
ADD_DEPENDENCIES(paddlex_inference ext-yaml-cpp)
target_link_libraries(paddlex_inference ${DEPS})

add_executable(classifier demo/classifier.cpp src/transforms.cpp src/paddlex.cpp)
ADD_DEPENDENCIES(classifier ext-yaml-cpp)
target_link_libraries(classifier ${DEPS})

add_executable(detector demo/detector.cpp src/transforms.cpp src/paddlex.cpp src/visualize.cpp)
ADD_DEPENDENCIES(detector ext-yaml-cpp)
target_link_libraries(detector ${DEPS})

add_executable(segmenter demo/segmenter.cpp src/transforms.cpp src/paddlex.cpp src/visualize.cpp)
ADD_DEPENDENCIES(segmenter ext-yaml-cpp)
target_link_libraries(segmenter ${DEPS})

add_executable(video_classifier demo/video_classifier.cpp src/transforms.cpp src/paddlex.cpp src/visualize.cpp)
ADD_DEPENDENCIES(video_classifier ext-yaml-cpp)
target_link_libraries(video_classifier ${DEPS})

add_executable(video_detector demo/video_detector.cpp src/transforms.cpp src/paddlex.cpp src/visualize.cpp)
ADD_DEPENDENCIES(video_detector ext-yaml-cpp)
target_link_libraries(video_detector ${DEPS})

add_executable(video_segmenter demo/video_segmenter.cpp src/transforms.cpp src/paddlex.cpp src/visualize.cpp)
ADD_DEPENDENCIES(video_segmenter ext-yaml-cpp)
target_link_libraries(video_segmenter ${DEPS})


if (WIN32 AND WITH_MKL)
    add_custom_command(TARGET classifier POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/mklml.dll ./paddlex_inference/mklml.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/libiomp5md.dll ./paddlex_inference/libiomp5md.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mkldnn/lib/mkldnn.dll ./paddlex_inference/mkldnn.dll
    )
    add_custom_command(TARGET detector POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/mklml.dll ./paddlex_inference/mklml.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/libiomp5md.dll ./paddlex_inference/libiomp5md.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mkldnn/lib/mkldnn.dll ./paddlex_inference/mkldnn.dll
    )
    add_custom_command(TARGET segmenter POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/mklml.dll ./paddlex_inference/mklml.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/libiomp5md.dll ./paddlex_inference/libiomp5md.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mkldnn/lib/mkldnn.dll ./paddlex_inference/mkldnn.dll
    )
    add_custom_command(TARGET video_classifier POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/mklml.dll ./paddlex_inference/mklml.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/libiomp5md.dll ./paddlex_inference/libiomp5md.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mkldnn/lib/mkldnn.dll ./paddlex_inference/mkldnn.dll
    )
    add_custom_command(TARGET video_detector POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/mklml.dll ./paddlex_inference/mklml.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/libiomp5md.dll ./paddlex_inference/libiomp5md.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mkldnn/lib/mkldnn.dll ./paddlex_inference/kldnn.dll
    )
    add_custom_command(TARGET video_segmenter POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/mklml.dll ./paddlex_inference/mklml.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mklml/lib/libiomp5md.dll ./paddlex_inference/libiomp5md.dll
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${PADDLE_DIR}/third_party/install/mkldnn/lib/mkldnn.dll ./paddlex_inference/mkldnn.dll
    )
    # for encryption
    if (EXISTS "${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll")
        add_custom_command(TARGET classifier POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./pmodel-decrypt.dll
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./release/pmodel-decrypt.dll
        )
        add_custom_command(TARGET detector POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./pmodel-decrypt.dll
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./release/pmodel-decrypt.dll
        )
        add_custom_command(TARGET segmenter POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./pmodel-decrypt.dll
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./release/pmodel-decrypt.dll
        )
        add_custom_command(TARGET video_classifier POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./pmodel-decrypt.dll
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./release/pmodel-decrypt.dll
        )
        add_custom_command(TARGET video_detector POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./pmodel-decrypt.dll
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./release/pmodel-decrypt.dll
        )
        add_custom_command(TARGET video_segmenter POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./pmodel-decrypt.dll
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ENCRYPTION_DIR}/lib/pmodel-decrypt.dll ./release/pmodel-decrypt.dll
        )
    endif()
endif()

file(COPY  "${CMAKE_SOURCE_DIR}/include/paddlex/visualize.h"
DESTINATION  "${CMAKE_BINARY_DIR}/include/"  )
file(COPY  "${CMAKE_SOURCE_DIR}/include/paddlex/config_parser.h"
DESTINATION  "${CMAKE_BINARY_DIR}/include/"  )
file(COPY  "${CMAKE_SOURCE_DIR}/include/paddlex/transforms.h"
DESTINATION  "${CMAKE_BINARY_DIR}/include/"  )
file(COPY  "${CMAKE_SOURCE_DIR}/include/paddlex/results.h"
DESTINATION  "${CMAKE_BINARY_DIR}/include/"  )
file(COPY  "${CMAKE_SOURCE_DIR}/include/paddlex/paddlex.h"
DESTINATION  "${CMAKE_BINARY_DIR}/include/"  )
