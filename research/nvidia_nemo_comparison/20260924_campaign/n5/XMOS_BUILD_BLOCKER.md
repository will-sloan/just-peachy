# XMOS ARM64 host/control-map packaging gate

Status: ACCESS_LICENSE_REVIEW_REQUIRED for a new vendor-source build/package;
physical firmware ABI remains CM5_HARDWARE_NOT_TESTED. No vendor source, binary
or firmware is added to the new N5 archives or Git backup.

Inspected existing prepared source archive:
`G:\Just_Peachy_PROTO1\cm5_bringup_20260922\native-xvf-usb-src.tar.gz`, SHA-256
`7f4f19eb6ea6b9a992b16614b723e032169720853ed15244da6c18819b11e715`.
Its local source receipt binds host-control 3.0.0 ZIP
`1e2fd4816df6f6814ba440afd5f854088bf995c6cea2c0b547f37f7202c11aaf`
and XVF3800 software 3.2.1 ZIP
`8a2181f6bc1a259c2dd869a2e488d2ef4a7730898408d81e292415ca33032a49`.
The CMake preparation admits aarch64 command-map output and excludes the ARM32
SPI library. A cross-build also needs a target libusb header/link closure.

Both local `host/LICENSE.rst` (January 2023) and `firmware/LICENSE.rst`
(June 2023) contain this condition:

> the Licensee is a business and will be using the Software for business purposes

The campaign authorizes ordinary commercially usable terms but expressly forbids
a false business attestation. Existing downloaded archives and older Pi build
receipts do not establish that factual condition or the permitted redistribution
scope for this new bundle. No new attestation was made. Confirm the applicable
existing XMOS entitlement or obtain compatible vendor terms before a new build
or distributable host/control package. This is a licensing-scope gate, not a
claim that the code cannot compile on ARM64 or that the user lacks a license.

Historical September 22 evidence records native-helper hashes on the earlier
Pi installation. Those are not actual local N5 binaries, not a fresh architecture
audit, and not evidence of the future device's firmware/pin configuration.
They are not promoted into this campaign's offline acceptance. Once permission
scope is established, build the matched host/command-map using the pinned
cross-toolchain, audit every ELF/dependency, and inspect help/version without
USB discovery before any later physical readback. Do not ship the older ARM32
vendor tools as ARM64, change firmware, or contact the offline Pi.
