// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#ifndef SHF_INIT_
#define SHF_INIT_

#include <platform.h>
#include <xcore/channel.h>

/*============================================================================*
 *                                                                            *
 * Name          : SHF_Init_AEC                                               *
 *                                                                            *
 * Description   : Initializes the BeClear AEC and Beamformer module.         *
 *                                                                            *
 * Pre           : mem          : Pointer to BeClear memory block             *
 *                 Nfar         : Number of far-end channels, see             *
 *                                BeClearCommon.h                             *
 *                 Nmics        : Number of microphones, see BeClearCommon.h  *
 *                 micpos       : Matrix containing cartesian coordinates of  *
 *                                the mics in meters, Nmics x 3 [x ,y, z]     *
 *                                float. The z coordinate must be zero.       *
 *                 array_type   : Indicates linear (1) or circular array (2). *
 *                 Naec         : Number of coefficients in the AEC filter,   *
 *                                see BeClearCommon.h                         *
 *                 Nbeams       : Number of focused beams, see BeClearCommon.h*
 *                 chan         : Channel for synchronization between AEC and *
 *                                PP tiles.                                   *
 * Post          : none         : Memory allocated and algorithm initialized. *
 *                                                                            *
 *============================================================================*/
void SHF_Init_AEC
(
    void * mem,
    const size_t Nfar,
    const size_t Nmics,
    const float * const * const micpos,
    const int array_type,
    const size_t Naec,
    const size_t Nbeams,
    chanend_t * chan
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_Init_AEC_split_post                 *
 *                                                                            *
 * Description   : Initializes the BeClear AEC and Beamformer module.         *
 *                                                                            *
 * Pre           : mem          : Pointer to BeClear memory block             *
 *                 micpos       : Matrix containing cartesian coordinates of  *
 *                                the mics in meters, Nmics x 3 [x ,y z]      *
 *                                float.                                      *
 *                 array_type   : Indicates linear or circular array (enum).  *
 *                                                                            *
 * Post          : none         : Memory allocated and algorithm initialized. *
 *                                                                            *
 *============================================================================*/
void SHF_Init_AEC_split_post
(
    void * mem,
    const float * const * const micpos,
    const int array_type,
    chanend_t * chan
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_Init_PP                                                *
 *                                                                            *
 * Description   : Initializes the BeClear Post processor module.             *
 *                                                                            *
 * Pre           : mem          : Pointer to BeClear memory block             *
 *                 chan         : Chanend for synchronization between AEC and *
 *                                PP tiles.                                   *
 * Post          : none         : Memory allocated and algorithm initialized. *
 *                                                                            *
 *============================================================================*/
void SHF_Init_PP
(
    void * mem,
    chanend_t * chan
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_Init_PP_split_post                                     *
 *                                                                            *
 * Description   : Initializes the BeClear Post processor module part 2.      *
 *                                                                            *
 * Pre           : mem          : Pointer to BeClear memory block             *
 *                 chan         : Chanend for synchronization between AEC and *
 *                                PP tiles.                                   *
 * Post          : none         : Memory allocated and algorithm initialized. *
 *                                                                            *
 *============================================================================*/
void SHF_Init_PP_split_post
(
    void * mem,
    chanend_t * chan
);

#endif
