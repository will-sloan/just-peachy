/*============================================================================*
 *                                                                            *
 * Filename     : BeClearCommon.h                                             *
 * Package      : BeClear                                                     *
 * Description  : Common properties of BeClear algorithms.                    *
 *                                                                            *
 * Copyright (C) Koninklijke Philips N.V., 2021.                              *
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
#ifndef _BECLEAR_COMMON_H
#define _BECLEAR_COMMON_H

/*============================================================================*/
/* Included modules.                                                          */
/*============================================================================*/

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
/* Customer name                                                              */
/*----------------------------------------------------------------------------*/
#define BECLEAR_CUSTOMER_NAME               "XMOS Ltd"

/*----------------------------------------------------------------------------*/
/* Application number                                                         */
/*----------------------------------------------------------------------------*/
#define BECLEAR_APPLICATION_MAJOR           1
#define BECLEAR_APPLICATION_MINOR           0

/*----------------------------------------------------------------------------*/
/* Library version                                                            */
/*----------------------------------------------------------------------------*/
#define BECLEAR_LIBRARY_MAJOR               3
#define BECLEAR_LIBRARY_MINOR               0
#define BECLEAR_LIBRARY_PATCH               0

/*----------------------------------------------------------------------------*/
/* Additional included libraries                                              */
/*----------------------------------------------------------------------------*/

/*----------------------------------------------------------------------------*/
/* Algorithm configuration                                                    */
/*----------------------------------------------------------------------------*/
#define BECLEAR_MAX_SAMPLE                  32767     /* maximum sample value */
#define BECLEAR_MIN_SAMPLE                 -32768     /* minimum sample value */

#define BECLEAR_SAMPLES_PER_FRAME           256       /* samples per frame    */
#define BECLEAR_SAMPLE_FREQUENCY            16000.0f  /* sample frequency     */

#define BECLEAR_MIN_NUMBER_OF_MICS          4         /* 4                    */
#define BECLEAR_MAX_NUMBER_OF_MICS          4         /* 8                    */

#define BECLEAR_MIN_NUMBER_OF_FARENDS       1         /* 1                    */
#define BECLEAR_MAX_NUMBER_OF_FARENDS       1         /* 2                    */

#define BECLEAR_NUMBER_OF_BEAMS             2         /* 4                    */

#define BECLEAR_NUMBER_OF_OUTPUTS           4         /* 6                    */

#define BECLEAR_MIN_AEC_LENGTH              2048      /* 256 ms (4096/16000)  */
#define BECLEAR_MAX_AEC_LENGTH              3072

#define BECLEAR_LINEAR_ARRAY                1
#define BECLEAR_CIRCULAR_ARRAY              2

/*============================================================================*/
/* Function prototypes.                                                       */
/*============================================================================*/

/*============================================================================*
 *                                                                            *
 * Name          : BeClear_ShowContactInformation                             *
 *                                                                            *
 * Description   : Prints contact information.                                *
 *                                                                            *
 * Pre           : none         :                                             *
 *                                                                            *
 * Post          : none         :                                             *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void BeClear_ShowContactInformation
(
    void
);

/*============================================================================*
 *                                                                            *
 * Name          : BeClear_ShowCustomerInformation                            *
 *                                                                            *
 * Description   : Prints customer information.                               *
 *                                                                            *
 * Pre           : none         :                                             *
 *                                                                            *
 * Post          : none         :                                             *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void BeClear_ShowCustomerInformation
(
    void
);

/*============================================================================*
 *                                                                            *
 * Name          : BeClear_ShowExpirationDate                                 *
 *                                                                            *
 * Description   : Prints expiration date of the BeClear library.             *
 *                 Date is printed in DD-MM-YYYY format.                      *
 *                                                                            *
 * Pre           : none         :                                             *
 *                                                                            *
 * Post          : none         :                                             *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void BeClear_ShowExpirationDate
(
    void
);

/*============================================================================*
 *                                                                            *
 * Name          : BeClear_CheckShelfLife                                     *
 *                                                                            *
 * Description   : Evaluates shelf life of BeClear library.                   *
 *                                                                            *
 * Pre           : none         :                                             *
 *                                                                            *
 * Post          : return       : Return nonzero if expiration date reached.  *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
int BeClear_CheckShelfLife
(
    void
);

/*============================================================================*
 *                                                                            *
 * Name          : BeClear_ShowVersion                                        *
 *                                                                            *
 * Description   : Prints version of BeClear library.                         *
 *                                                                            *
 * Pre           : none         :                                             *
 *                                                                            *
 * Post          : none         :                                             *
 *                                                                            *
 * Comments      :                                                            *
 *                                                                            *
 *============================================================================*/
void BeClear_ShowVersion
(
    void
);

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
