// Copyright 2022-2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// API that must be fulfilled for shf_wrapper to be able to set the correct startup
/// defaults for the SHF algorithm. Done as struct rather than macros to provide more
/// useful type checking etc.
#ifndef SHF_DEFAULTS_H
#define SHF_DEFAULTS_H

/// @brief mic array geometry as used in AEC
/// Each microphone is represented by 3 XYZ coordinates in cm.
typedef struct {
    float mic0[3];
    float mic1[3];
    float mic2[3];
    float mic3[3];
} shf_defaults_mic_geo_t;

/// @brief aec parameters, names approximately match the writable parameters for AEC
typedef struct {
    int                 hpfonoff;
    float               aecsilencelevel[ 2 ];
    int                 aecemphasisonoff;
    float               far_extgain;
    float               pcd_couplingi;
    float               pcd_minthr;
    float               pcd_maxthr;
    int                 asroutonoff;
    float               asroutgain;
    int                 fixedbeamsonoff;
    float               fixedbeamnoisethr[ 2 ];
    float               fixedbeamsazimuth_values[ 2 ];
    float               fixedbeamselevation_values[ 2 ];
    int                 fixedbeamsgating;
} shf_defaults_aec_t;

/// @brief pp tile parameters, names approximately match the writable parameters for
/// the PP tile
typedef struct {
    int                 agconoff;
    float               agcmaxgain;
    float               agcdesiredlevel;
    float               agcgain;
    float               agctime;
    float               agcfasttime;
    float               agcalphafastgain;
    float               agcalphaslow;
    float               agcalphafast;
    int                 limitonoff;
    float               limitplimit;
    float               min_ns;
    float               min_nn;
    int                 echoonoff;
    float               gamma_e;
    float               gamma_etail;
    float               gamma_enl;
    int                 nlattenonoff;
    int                 nlaec_mode;
    float               mgscale[ 3 ];
    float               fmin_speindex;
    int                 dtsensitive;
    int                 attns_mode;
    float               attns_nominal;
    float               attns_slope;
} shf_defaults_pp_t;

/// @brief Getter for microphone geometry, the array in the struct must be static
const shf_defaults_mic_geo_t* shf_defaults_get_mic_geo();

/// @brief Getter for the shf defaults on the PP tile. As it will be used after this function call
/// the pointer it returns should reference a static struct containing valid values for _all_ of the
/// fields within.
const shf_defaults_pp_t* shf_defaults_get_pp();

/// @brief AEC version of shf_defaults_aec_t
const shf_defaults_aec_t* shf_defaults_get_aec();

const float* shf_defaults_get_nlmodel_all(int* rows, int* cols);

const float* shf_defaults_get_eq_filter_all(int* bands);

void init_aec_parameters(void);
void init_pp_parameters(void);

#endif
