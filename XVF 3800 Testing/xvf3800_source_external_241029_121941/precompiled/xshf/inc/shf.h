// Copyright 2022-2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#ifndef _SHF_MAIN
#define _SHF_MAIN

/*============================================================================*/
/* Included modules.                                                          */
/*============================================================================*/
#include <stddef.h> /* size_t */
#include <stdbool.h>
#include <xcore/channel.h>
#include "BeClearMemory.h"

/*============================================================================*/
/* C++ protection.                                                            */
/*============================================================================*/
#ifdef __cplusplus
extern "C" {
#endif

#define SHF_AEC_LENGTH 3072

#ifndef SHF_NUM_BANDS // set by cmake
#error
#endif

/*============================================================================*/
/* Compatibility Macros for SWB to allow common wrapper                       */
/*============================================================================*/
void* SHF_GetMemory_AEC(void);

void* SHF_GetMemory_PP(void);


// SWB specific functions for synchronising with the remote tile SHF that map to nothing for the non-SWB case
void SHF_Sync_bypass_with_remote(int8_t);
void SHF_Signal_control_done_to_remote_AEC(void);
void SHF_Signal_control_done_to_remote_PP(void);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_Main_AEC                                               *
 *                                                                            *
 * Description   : Performs processing of the signals.                        *
 *                                                                            *
 * Pre           : mics         : matrix of Nmics x B floats containing the   *
 *                                microphone signals.                         *
 *                 spks         : matrix of Nfar x B floats containing the    *
 *                                far-end reference signals.                  *
 *                 qcom         : matrix of size BECLEAR_NUMBER_OF_OUTPUTS x B*
 *                 aecmics      : matrix of size Nmics x B.                   *
 *                                                                            *
 * Post          : qcom         : Communication output signals.               *
 *                 aecmics      : AEC residual signals.                       *
 *                                                                            *
 * Comments      : B is equal to BECLEAR_SAMPLES_PER_FRAME. The input and     *
 *                 output signals start at a memory address that is a multiple*
 *                 of 8 bytes. See testBeClearSuperHandsFree.c                *
 *                                                                            *
 *============================================================================*/
void SHF_Main_AEC
(
    float * const * const mics,
    float * const * const spks,
    float * const * const qcom,
    float * const * const aecmics
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_Close_AEC                                              *
 *                                                                            *
 * Description   : Releases memory on AEC tile.                               *
 *                                                                            *
 * Pre           : none                                                       *
 *                                                                            *
 * Post          : none         : Allocated memory has been released.         *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void SHF_Close_AEC
(
    void
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_SetPar_AEC                                             *
 *                                                                            *
 * Description   : Sets values of BeClear SuperHandsFree AEC parameters.      *
 *                                                                            *
 * Pre           : param        : Parameter id defined in                     *
 *                                BeClearSuperHandsFree.h.                    *
 *                 valptr       : Pointer to variable of correct type.        *
 *                                                                            *
 * Post          : none         : New parameter value is set.                 *
 *                                                                            *
 * Comments      : See BeClearSuperHandsFree.h for parameter definitions,     *
 *                 types, ranges and default values.                          *
 *                                                                            *
 *============================================================================*/
void SHF_SetPar_AEC
(
    int param,
    void * valptr
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_GetPar_AEC                                             *
 *                                                                            *
 * Description   : Gets values of BeClear SuperHandsFree AEC parameters.      *
 *                                                                            *
 * Pre           : param        : Parameter id defined in                     *
 *                                BeClearSuperHandsFree.h.                    *
 *                 valptr       : Pointer to variable of correct type.        *
 *                                                                            *
 * Post          : valptr       : Contains requested parameter value.         *
 *                                                                            *
 * Comments      : See BeClearSuperHandsFree.h for parameter definitions,     *
 *                 types, ranges and default values.                          *
 *                                                                            *
 *============================================================================*/
void SHF_GetPar_AEC
(
    int param,
    void * valptr
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_SetAECCoefs_AEC                                        *
 *                                                                            *
 * Description   : Sets the time-domain AEC filter coefficients.              *
 *                                                                            *
 * Pre           : farindex     : Far-end index [0 .. Nfar-1].                *
 *                 micindex     : Microphone index [0 .. Nmics-1].            *
 *                 chunkindex   : Index of chunk (256 samples) to read.       *
 *                 wt           : Float vector of size Naec containing the    *
 *                                time-domain AEC coefficients.               *
 *                                                                            *
 * Post          : none         : New AEC coefficients are set.               *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void SHF_SetAECCoefs_AEC
(
    size_t farindex,
    size_t micindex,
    size_t chunkindex,
    const float * const wt
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_GetAECCoefs_AEC                                        *
 *                                                                            *
 * Description   : Gets the time-domain AEC filter coefficients.              *
 *                                                                            *
 * Pre           : farindex     : Far-end index [0 .. Nfar-1].                *
 *                 micindex     : Microphone index [0 .. Nmics-1].            *
 *                 chunkindex   : Index of chunk (256 samples) to set.        *
 *                 wt           : Float vector of size Naec.                  *
 *                                                                            *
 * Post          : wt           : Contains the time-domain AEC coefficients.  *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void SHF_GetAECCoefs_AEC
(
    size_t farindex,
    size_t micindex,
    size_t chunkindex,
    float * const wt
);

/*============================================================================*/
/* Function prototypes for PostProcessor tile.                                */
/*============================================================================*/

/*============================================================================*
 *                                                                            *
 * Name          : SHF_Main_PP                                                *
 *                                                                            *
 * Description   : Performs main processing on PP tile.                       *
 *                                                                            *
 * Pre           : none                                                       *
 *                                                                            *
 * Post          : none         :                                             *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void SHF_Main_PP
(
    void
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_Close_PP                                               *
 *                                                                            *
 * Description   : Releases memory.                                           *
 *                                                                            *
 * Pre           : none                                                       *
 *                                                                            *
 * Post          : none         : Allocated memory has been released.         *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void SHF_Close_PP
(
    void
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_SetPar_PP                                              *
 *                                                                            *
 * Description   : Sets values of BeClear SuperHandsFree PP parameters.       *
 *                                                                            *
 * Pre           : param        : Parameter id defined in                     *
 *                                BeClearSuperHandsFree.h.                    *
 *                 valptr       : Pointer to variable of correct type.        *
 *                                                                            *
 * Post          : none         : New parameter value is set.                 *
 *                                                                            *
 * Comments      : See BeClearSuperHandsFree.h for parameter definitions,     *
 *                 types, ranges and default values.                          *
 *                                                                            *
 *============================================================================*/
void SHF_SetPar_PP
(
    int param,
    void * valptr
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_GetPar_PP                                              *
 *                                                                            *
 * Description   : Gets values of BeClear SuperHandsFree PP parameters.       *
 *                                                                            *
 * Pre           : param        : Parameter id defined in                     *
 *                                BeClearSuperHandsFree.h.                    *
 *                 valptr       : Pointer to variable of correct type.        *
 *                                                                            *
 * Post          : valptr       : Contains requested parameter value.         *
 *                                                                            *
 * Comments      : See BeClearSuperHandsFree.h for parameter definitions,     *
 *                 types, ranges and default values.                          *
 *                                                                            *
 *============================================================================*/
void SHF_GetPar_PP
(
    int param,
    void * valptr
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_GetNLModelSize_PP                                      *
 *                                                                            *
 * Description   : Gets the size of the non-linear model for non-linear echo  *
 *                 suppression.                                               *
 *                                                                            *
 * Pre           : NRow         : Pointer to variable of type size_t.         *
 *                 NCol         : Pointer to variable of type size_t.         *
 *                                                                            *
 * Post          : NRow         : Number of rows of the non-linear model.     *
 *                 NCol         : Number of columns of the non-linear model.  *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void SHF_GetNLModelSize_PP
(
    uint8_t band,
    size_t * NRow,
    size_t * NCol
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_SetNLModel_PP                                          *
 *                                                                            *
 * Description   : Sets the non-linear model for non-linear echo suppression. *
 *                                                                            *
 * Pre           : NRow         : Number of rows in the non-linear matrix.    *
 *                 NCol         : Number of columns in the non-linear matrix. *
 *                 m            : Matrix of size NRow x NCol containing the   *
 *                                non-linear model.                           *
 *                                                                            *
 * Post          : none         : The non-linear model is set.                *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void SHF_SetNLModel_PP
(
    size_t NRow,
    size_t NCol,
    const float * const * const m
);

/*============================================================================*
 *                                                                            *
 * Name          : SHF_GetNLModel_PP                                          *
 *                                                                            *
 * Description   : Gets the non-linear model for non-linear echo suppression. *
 *                                                                            *
 * Pre           : NRow         : Number of rows in the non-linear matrix.    *
 *                 NCol         : Number of columns in the non-linear matrix. *
 *                 m            : Float matrix of size NRow x NCol.           *
 *                                                                            *
 * Post          : m            : Contains the non-linear model.              *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void SHF_GetNLModel_PP
(
    size_t NRow,
    size_t NCol,
    float * const * const m
);

/// @brief Max number of rows expected in the PP NL Model buffer
#define MAX_NL_MODEL_ROWS (16)
/// @brief Max number of columns expected in the PP NL Model buffer
#define MAX_NL_MODEL_COLS (40)
/// @brief Numbers of bands expected in the PP EQ filter
#define WB_EQ_BANDS  (40)
#define SWB_EQ_BANDS (56)

/// @brief  Wrapper function for setting the Non Linear model for the device
/// @param band Band index. 0 for low band, 1 for high band
/// @param nlmodel_buf Buffer containing the NL Model coefficients we want to write to the device
void SHF_Set_NLmodel
(
    uint8_t band,
    const float* nlmodel_buf
);

/// @brief  Wrapper function for reading the Non-Linear model from the device
/// @param band Band index. 0 for low band, 1 for high band
/// @param nlmodel_buf Buffer to store the NL model coefficients in.
void SHF_Get_NLmodel
(
    uint8_t band,
    float *nlmodel_buf
);

/// @brief  Check if a given command index corresponds to a SHF AEC or PP command
/// @param index Command index
/// @return true if the command index is for a SHF command, false otherwise
bool SHF_Is_SHF_command_index( int8_t index );

/// @brief Get azimuth values and associated speech power level for all 4 beams
/// @param azimuths Array for storing the azimuth values.
/// @param spenergy Array for storing the spenergy values.
/// @param num_azimuths Expected number of azimuth values.
void SHF_Get_azimuths
(
    float *azimuths,
    float *spenergy,
    size_t num_azimuths
);

/// @brief Get stored azimuth values for the beams in fixed beam mode
/// @param azimuths Array for storing the azimuth values.
/// @param elevation Array for storing the elevation values.
/// @param num_beams Number of beams.
void SHF_Get_fixed_beams_azimuths
(
    float *azimuths,
    float *elevation,
    size_t num_beams
);

/// @brief Set azimuth values for the beams in fixed beam mode
/// @param azimuths Array with the azimuth values.
/// @param elevation Array with the elevation values.
/// @param num_beams Number of beams.
void SHF_Set_fixed_beams_azimuths
(
    float *azimuths,
    float *elevation,
    size_t num_beams
);

/// @brief Get number of bands used for the equalization filter
/// @param Nbands Pointer for storing number of bands.
void SHF_Get_EQNbands
(
    size_t * Nbands
);

/// @brief Set gains of equalization filter per frequency band
/// @param eq Array with equalization gains.
void SHF_Set_EQ
(
    const float * eq
);

/// @brief Get gains of equalization filter per frequency band
/// @param eq Array for storing equalization gains.
void SHF_Get_EQ
(
    float * eq
);

/*============================================================================*/
/* Close when C++ protected.                                                  */
/*============================================================================*/
#ifdef __cplusplus
}
#endif

/*============================================================================*/
/* End of multiple inclusion protection.                                      */
/*============================================================================*/
#endif
