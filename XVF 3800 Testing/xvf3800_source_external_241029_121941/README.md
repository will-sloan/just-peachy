# XVF3800 Repository

XVF3800 is a voice conferencing reference application which utilises an audio pipeline to provide high quality audio conferencing products.
For more information about features and usage, see the documentation.

## Release package structure

The file structure of the release package is listed below:

```
├── CHANGELOG.rst    <- list of changes of current and past releases
├── LICENSE.rst      <- license file
├── precompiled      <- folder containing the precompiled libraries included in the XVF3800 builds
├── README.md        <- this readme file
└── sources          <- folder containing the source files necessary to build the XVF3800 applications
```

## Requirements

The following tools must be installed:

  - python3 (version 3.10 only; versions above 3.10 are currently unsupported)
  - pip3
  - cmake (version 3.21 or higher)
  - XMOS tools (version 15.2.1 or higher)
  - ninja (Windows only; version 1.11.1 or higher)

## Building

To build the firmware from the release package:

    # Go to the source folder
    cd sources

    # Install the required Python3 packages
    pip3 install -r requirements_build.txt

    # See available configurations
    cmake --list-presets

    # Configure chosen configuration
    # This step can take several minutes
    cmake --preset=rel_app_xvf3800
    # Or for windows
    cmake --preset=rel_app_xvf3800_windows

    # See available build presets
    cmake --build --list-presets

    # Build chosen preset
    cmake --build --preset=ua-io48-lin

The generated binary is saved in `sources/build/`

## Running

To load the firmware on the board use:

````
# flash your chosen binary
xflash build/application_xvf3800_ua-io48-lin.xe
````

**Note:** The XTC Tools applications, such as xflash, are only available for
Windows, Linux, or macOS. The host application, xvf_host, is available for
Windows, Linux, macOS, and Raspberry Pi OS.

To use the control host application, do the following:

    1. Copy all the contents of the appropriate subdirectory in *host_vX.Y.Z* to the development machine connected to the board.
       The subdirectories appear in the binary release package, and they are named after the operating system,
       i.e. win32, linux_x86_64, etc.

    2. Open a terminal and go the *host_vX.Y.Z/<OS>* directory

    3. Look at the options in the help menu by typing on Windows:

````
xvf_host.exe -h
````

       and on Linux, macOS and Raspberry Pi OS:

````
./xvf_host -h
````

   **Note:** To read/write control parameters via SPI, the application must be called with *sudo*

## Documentation

Detailed usage, configuration and design documentation for XVF3800 is provided in the documentation package available from https://www.xmos.com/develop/xvf3800/.

## License

The software in this repository is subject to the terms of the [XCORE VocalFusion license](./LICENSE.rst)

