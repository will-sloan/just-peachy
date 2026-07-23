/*============================================================================*
 *                                                                            *
 * Filename     : BeClearMemory.h                                             *
 * Package      : Beclear                                                     *
 * Description  : Exposes memory usage required by BeClear (read-only)        *
 *                                                                            *
 * Copyright (C) Koninklijke Philips N.V., 2022.                              *
 *                                                                            *
 * All rights reserved.                                                       *
 * This source code and any compilation or derivative thereof is the          *
 * proprietary information of Royal Philips and is confidential in nature.    *
 * Under no circumstances is this software to be combined with any Open Source*
 * Software in any way or placed under an Open Source License of any type     *
 * without the express written permission of Royal Philips.                   *
 *                                                                            *
 *============================================================================*/

/*============================================================================*/
/* Multiple inclusion protection.                                             */
/*============================================================================*/
#ifndef _BECLEAR_MEMORY_H
#define _BECLEAR_MEMORY_H

/*============================================================================*/
/* Included modules.                                                          */
/*============================================================================*/
#include "shf_XMOS_memory_xs3.h"

/*============================================================================*/
/* C++ protection.                                                            */
/*============================================================================*/
#ifdef __cplusplus
extern "C" {
#endif

/*============================================================================*/
/* Constants and Macros for this module.                                      */
/*============================================================================*/

/*----------------------------------------------------------------------------*/
/* AEC Tile memory (read-only)                                                */
/*----------------------------------------------------------------------------*/
#define BECLEAR_AEC_TMEM                      2100
#define BECLEAR_AEC_THREAD0_TMEM              SHF_AEC_THREAD0_TMEM
#define BECLEAR_AEC_THREAD1_TMEM              SHF_AEC_THREAD1_TMEM
#define BECLEAR_AEC_THREAD2_TMEM              SHF_AEC_THREAD2_TMEM
#define BECLEAR_AEC_THREAD3_TMEM              SHF_AEC_THREAD3_TMEM

#define BECLEAR_MEMSIZE_AEC_OBJ 40
#define BECLEAR_MEMSIZE_AEC_CMEM 228264
#define BECLEAR_MEMSIZE_AEC_TMEM ( \
            BECLEAR_AEC_TMEM + \
            BECLEAR_AEC_THREAD0_TMEM + \
            BECLEAR_AEC_THREAD1_TMEM + \
            BECLEAR_AEC_THREAD2_TMEM + \
            BECLEAR_AEC_THREAD3_TMEM )

#define BECLEAR_MEMSIZE_AEC ( \
            BECLEAR_MEMSIZE_AEC_OBJ + \
            BECLEAR_MEMSIZE_AEC_CMEM + \
            BECLEAR_MEMSIZE_AEC_TMEM )

/*----------------------------------------------------------------------------*/
/* PP Tile memory (read-only)                                                 */
/*----------------------------------------------------------------------------*/
#define BECLEAR_PP_TMEM                       0
#define BECLEAR_PP_THREAD0_TMEM               SHF_PP_THREAD0_TMEM
#define BECLEAR_PP_THREAD1_TMEM               SHF_PP_THREAD1_TMEM
#define BECLEAR_PP_THREAD2_TMEM               SHF_PP_THREAD2_TMEM

#define BECLEAR_MEMSIZE_PP_OBJ 40
#define BECLEAR_MEMSIZE_PP_CMEM 156328
#define BECLEAR_MEMSIZE_PP_TMEM ( \
            BECLEAR_PP_TMEM + \
            BECLEAR_PP_THREAD0_TMEM + \
            BECLEAR_PP_THREAD1_TMEM + \
            BECLEAR_PP_THREAD2_TMEM )

#define BECLEAR_MEMSIZE_PP ( \
            BECLEAR_MEMSIZE_PP_OBJ + \
            BECLEAR_MEMSIZE_PP_CMEM + \
            BECLEAR_MEMSIZE_PP_TMEM )

#ifndef __ASSEMBLER__
/*============================================================================*/
/* Function prototypes.                                                       */
/*============================================================================*/
void * BeClear_GetMemory_AEC( void );
void * BeClear_GetMemory_PP( void );
#endif

/*============================================================================*/
/* C++ protection.                                                            */
/*============================================================================*/
#ifdef __cplusplus
}
#endif

/*============================================================================*/
/* Multiple inclusion protection.                                             */
/*============================================================================*/
#endif
