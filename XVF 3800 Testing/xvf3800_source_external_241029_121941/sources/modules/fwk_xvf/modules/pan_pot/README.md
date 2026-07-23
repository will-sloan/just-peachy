# Pan pot

Library for panning mono to stereo based on an angle.
[See this link for description of the different panning algorithms](https://www.cs.cmu.edu/~music/icm-online/readings/panlaws/#pan-laws)

This provides two implementations of the -4.5 dB panning law and one of the linear panning law. All
have been modified to pan from 0 to π/2 radians. This differs from the website above which uses
0 to π/4 radians.

The reason for two implementations of -4.5 dB is that it is an expensive operation so a lookup table
approach is supplied. The python script used to generate the lookup table is also provided. The
generation happens automatically in CMakeLists.txt

