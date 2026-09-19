/* Local XVF capture UI. Hardware ownership and quality decisions belong to the server. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const form = $('setup-form');
  const STORE_KEY = 'just-peachy-xvf-setup-v2';
  const state = { connected: false, initializing: true, busy: false, pending: false, status: {}, profiles: [], devices: [], excitations: [], metricCache: new Map(), telemetrySignature: '', telemetrySeenAt: null, resultSignature: '', runId: null };
  let archiveLoaded = false, archiveLoading = false;
  let recoveryGeneration = null;
  let latestDeletable = null;
  const numberFields = ['source_distance_m', 'source_angle_deg', 'source_x_m', 'source_y_m', 'source_z_m', 'source_height_m', 'source_facing_yaw_deg', 'source_facing_pitch_deg', 'device_height_m', 'device_yaw_deg', 'device_pitch_deg', 'device_roll_deg', 'device_x_m', 'device_y_m', 'device_z_m', 'os_volume_pct'];
  const metricNames = {
    AEC_AZIMUTH_VALUES: 'Beam directions · native radians',
    AEC_SPENERGY_VALUES: 'Beam speech energy · device units',
    AUDIO_MGR_SELECTED_AZIMUTHS: 'Selected output angles · native radians',
  };
  const field = name => form.elements.namedItem(name);
  const textValue = name => (field(name)?.value ?? '').trim() || null;
  const numericValue = name => {
    const raw = textValue(name);
    if (raw === null) return null;
    const value = Number(raw);
    if (!Number.isFinite(value)) throw new Error(`Enter a finite number for ${name.replaceAll('_', ' ')} or leave it blank.`);
    return value;
  };
  const hostApiName = device => typeof device?.hostapi_name === 'string' ? device.hostapi_name : typeof device?.hostapi === 'string' ? device.hostapi : null;
  const referenceDeviceMatches = (device, fingerprint) => Boolean(device && fingerprint.reference_device_name && fingerprint.reference_hostapi_name && device.name === fingerprint.reference_device_name && hostApiName(device) === fingerprint.reference_hostapi_name && device.approved_for_reference === true);

  function notice(message, isError = false) {
    $('notice').textContent = message;
    $('notice').className = isError ? 'notice error' : 'notice';
    $('notice').hidden = !message;
  }
  async function api(path, body, timeout = 10000) {
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), timeout);
    try {
      const response = await fetch(path, { method: body === undefined ? 'GET' : 'POST', cache: 'no-store', headers: body === undefined ? {} : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal: abort.signal });
      const raw = await response.text();
      let data;
      try { data = raw ? JSON.parse(raw) : {}; } catch { throw new Error(`The recorder returned an unreadable response (${response.status}).`); }
      if (!response.ok || data.error) throw new Error(typeof data.error === 'string' ? data.error : data.message || `Recorder request failed (${response.status}).`);
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The recorder did not reply in time. Check its status before starting another run.');
      throw error;
    } finally { clearTimeout(timer); }
  }

  function formSnapshot() {
    const snapshot = { ui_schema_version: 3, hardware_context_version: 'krk-emm6-2026-09-06' };
    for (const control of form.elements) {
      if (!control.name || control.name === 'calibrator_operator_confirmed' || (control.type === 'radio' && !control.checked)) continue;
      snapshot[control.name] = control.type === 'checkbox' ? control.checked : control.value;
    }
    snapshot.profile_name = $('profile-name').value;
    const output = state.devices.find(device => String(device.index) === textValue('playback_device_index'));
    if (output) snapshot.playback_device_name = output.name;
    const reference = state.devices.find(device => String(device.index) === textValue('reference_device_index'));
    snapshot.reference_device_name = reference?.name ?? null;
    snapshot.reference_hostapi_name = hostApiName(reference);
    const playback = state.devices.find(device => String(device.index) === textValue('playback_device_index'));
    snapshot.playback_hostapi_name = hostApiName(playback);
    return snapshot;
  }
  function migrateHardwareSnapshot(original) {
    const snapshot = { ...original };
    if (snapshot.hardware_context_version === 'krk-emm6-2026-09-06') return snapshot;
    const oldSource = snapshot.speaker_model;
    if (!oldSource || /^Edifier\b/i.test(oldSource)) {
      snapshot.speaker_model = 'KRK GoAux 4';
      snapshot.speaker_connection = 'wired';
      snapshot.source_id = 'KRK_GOAUX4_01';
      snapshot.reference_enabled = false;
      snapshot.reference_microphone_model = 'Dayton Audio EMM-6';
      for (const key of ['reference_device_index', 'reference_device_name', 'reference_hostapi_name', 'reference_microphone_serial', 'reference_interface_gain_note', 'reference_calibration_file_path', 'reference_sensitivity_pa_per_fs', 'reference_calibration_record']) snapshot[key] = '';
      if (oldSource) {
        for (const key of ['speaker_volume_mark', 'bass_dial', 'treble_dial', 'os_volume_pct', 'playback_device_index', 'playback_device_name', 'speaker_cabling_note', 'source_facing_yaw_deg', 'source_facing_pitch_deg']) snapshot[key] = '';
        snapshot.calibration_label = 'Uncorrected; reference optional';
        snapshot.calibration_reference = '';
        snapshot.profile_name = 'KRK GoAux 4 — complete setup before recording';
        if (/EDIFIER/i.test(snapshot.trial_label || '')) snapshot.trial_label = 'KRK_P0_LEVEL_PILOT';
        snapshot.notes = [snapshot.notes, 'Hardware changed to KRK GoAux 4 / optional Dayton EMM-6 on 2026-09-06. Earlier source notes are historical. Enter KRK settings and reselect its wired output; prior speaker calibration is not transferred.'].filter(Boolean).join('\n');
      }
    }
    snapshot.reference_microphone_model ||= 'Dayton Audio EMM-6';
    snapshot.speaker_arc_state ??= 'unknown';
    snapshot.speaker_arc_note ??= '';
    snapshot.speaker_interface_output_level ??= '';
    snapshot.speaker_orientation_note ??= '';
    snapshot.hardware_context_version = 'krk-emm6-2026-09-06';
    return snapshot;
  }
  function applySnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== 'object') return;
    snapshot = migrateHardwareSnapshot(snapshot);
    snapshot.reference_enabled = snapshot.reference_enabled === true;
    snapshot.calibrator_operator_confirmed = false;
    snapshot.reference_device_index ??= '';
    for (const name of ['reference_microphone_model', 'reference_microphone_serial', 'reference_interface_gain_note', 'reference_placement_note', 'reference_distance_to_speaker_m', 'reference_calibration_file_path', 'reference_sensitivity_pa_per_fs', 'reference_calibration_record', 'calibrator_known_spl_db']) snapshot[name] ??= '';
    snapshot.reference_channel ??= '1';
    snapshot.calibrator_frequency_hz ??= '1000';
    if (![2, 3].includes(snapshot.ui_schema_version)) {
      snapshot.room_name ??= snapshot.room_id;
      snapshot.position_name ??= snapshot.placement_id;
      if (!['FLAT', 'UPRIGHT'].includes(snapshot.device_orientation)) delete snapshot.device_orientation;
      // A room angle cannot be reconstructed from native telemetry or board yaw.
    }
    if (snapshot.ui_schema_version !== 3 && (!snapshot.domain || snapshot.domain === 'both')) snapshot.domain = 'amplified';
    const legacyClutter = { typical: 'normal', controlled: 'unknown', other: 'unknown' };
    if (Object.hasOwn(legacyClutter, snapshot.clutter_state)) {
      const note = `Imported room clutter label: ${snapshot.clutter_state}.`;
      const existingNotes = typeof snapshot.notes === 'string' ? snapshot.notes.trim() : '';
      snapshot.notes = existingNotes.includes(note) ? existingNotes : [existingNotes, note].filter(Boolean).join('\n');
      snapshot.clutter_state = legacyClutter[snapshot.clutter_state];
    }
    for (const [name, value] of Object.entries(snapshot)) {
      if (name === 'profile_name') { $('profile-name').value = value ?? ''; continue; }
      const control = field(name);
      if (!control) continue;
      if (control.type === 'checkbox') control.checked = value === true;
      else control.value = value === null ? '' : String(value);
    }
    if (snapshot.playback_device_name && state.devices.length) {
      const selected = state.devices.find(device => String(device.index) === textValue('playback_device_index'));
      if (!selected || selected.name !== snapshot.playback_device_name) {
        field('playback_device_index').value = '';
        notice('The saved playback endpoint has changed. Select the current speaker output before measuring.', true);
      }
    }
    if (state.devices.length && textValue('reference_device_index') !== null) {
      const selected = state.devices.find(device => String(device.index) === textValue('reference_device_index'));
      if (!referenceDeviceMatches(selected, snapshot)) {
        field('reference_device_index').value = '';
        notice('The saved setup reference input is unavailable or changed. Routine array recording remains available; reselect it only for another speaker reference.');
      }
    }
    excitationDetail();
    outputDetail();
    updateSimpleUI();
  }
  function persist() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(formSnapshot())); }
    catch { notice('Browser storage is unavailable. Use Save setup to preserve your profile on this computer.', true); }
  }
  let restored = {};
  try { restored = JSON.parse(localStorage.getItem(STORE_KEY) || localStorage.getItem('just-peachy-xvf-setup-v1') || '{}'); } catch { /* A corrupted draft must not block capture. */ }
  applySnapshot(restored);

  function collectSetup() {
    const values = Object.fromEntries(numberFields.map(name => [name, numericValue(name)]));
    const provenance = {};
    for (const [name, value] of Object.entries(values)) {
      const orientation = /angle|yaw|pitch|roll/.test(name);
      provenance[name] = value === null ? 'unknown' : name === 'os_volume_pct' ? 'user_entered' : textValue(orientation ? 'orientation_basis' : 'position_basis') || 'unknown';
    }
    return {
      schema_version: '2.0', room_name: textValue('room_name'), position_name: textValue('position_name'),
      project_id: textValue('project_id'), room_id: textValue('room_id'), table_id: textValue('table_id'), placement_id: textValue('placement_id'),
      trial_label: textValue('trial_label'), pilot_phase: textValue('pilot_phase'), device_placement_id: textValue('device_placement_id'), source_facing: textValue('source_facing_label'), clutter_state: textValue('clutter_state'),
      obstruction: { present: field('obstructed').checked, notes: textValue('obstruction_notes') },
      source: { id: textValue('source_id'), position_m: { x: values.source_x_m, y: values.source_y_m, z: values.source_z_m }, distance_to_array_m: values.source_distance_m, azimuth_lab_deg: values.source_angle_deg, height_above_floor_m: values.source_height_m, facing_label: textValue('source_facing_label'), facing_yaw_deg: values.source_facing_yaw_deg, facing_pitch_deg: values.source_facing_pitch_deg },
      device: { orientation: textValue('device_orientation'), placement_id: textValue('device_placement_id'), position_m: { x: values.device_x_m, y: values.device_y_m, z: values.device_z_m }, height_above_floor_m: values.device_height_m, yaw_deg: values.device_yaw_deg, pitch_deg: values.device_pitch_deg, roll_deg: values.device_roll_deg },
      coordinate_frame: { origin: textValue('frame_origin'), positive_x: textValue('frame_x_axis'), positive_y: textValue('frame_y_axis'), positive_z: textValue('frame_z_axis'), axis_and_angle_notes: textValue('axis_notes'), protocol_azimuth_convention: '0 forward away from seated user; +90 seated left; -90 seated right; 180 toward seat', user_reported_mic_order_seated_left_to_right: ['MIC0', 'MIC1', 'MIC2', 'MIC3'], native_angle_transform_verified: false },
      metadata_provenance: provenance,
      photo_references: (textValue('photo_references') || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean),
      mic_gain_policy: 'keep_existing',
      hardware_context: { revision: 'krk-emm6-2026-09-06', campaign_source: 'KRK GoAux 4', optional_reference_microphone: 'Dayton Audio EMM-6', primary_rir_channels: ['MIC0', 'MIC1', 'MIC2', 'MIC3'], reference_required_for_normal_capture: false },
      speaker: { model_user_reported: textValue('speaker_model'), exact_model_verified: false, connection: textValue('speaker_connection'), bass_dial: textValue('bass_dial'), treble_dial: textValue('treble_dial'), eq_lf: textValue('bass_dial'), eq_hf: textValue('treble_dial'), arc_state_user_reported: textValue('speaker_arc_state'), arc_configuration_note: textValue('speaker_arc_note'), interface_output_level_user_note: textValue('speaker_interface_output_level'), orientation_user_note: textValue('speaker_orientation_note'), volume_mark: textValue('speaker_volume_mark'), os_volume_pct: values.os_volume_pct, cabling_and_cabinet_user_note: textValue('speaker_cabling_note'), physical_route_verified: false, controls_fixed_across_series_user_reported: field('speaker_settings_fixed').checked, automatic_equalization: false, automatic_equalization_scope: 'recorder software only; speaker ARC is logged separately', automatic_normalization: false },
      calibration: { status: 'relative_uncalibrated', label: textValue('calibration_label'), reference_record: textValue('calibration_reference'), reference_optional: true, reference_microphone_model: 'Dayton Audio EMM-6', source_correction_applied: false, source_correction_policy: 'deferred; retain reference archive for later synthetic-versus-real mismatch analysis' },
      interpretation: { angle_frame: 'native_device_uncalibrated', energy_units: 'native_device_metric', absolute_spl_calibrated: false },
      notes: textValue('notes'),
    };
  }
  function reveal(control) {
    let element = control instanceof RadioNodeList ? control[0] : control;
    for (let parent = element?.parentElement; parent; parent = parent.parentElement) if (parent.tagName === 'DETAILS') parent.open = true;
    element?.focus();
  }
  function requireField(name, valid, message) {
    if (!valid) { reveal(field(name)); throw new Error(message); }
  }
  function collectReference() {
    const enabled = field('reference_enabled').checked;
    const index = enabled ? numericValue('reference_device_index') : null;
    const device = state.devices.find(item => item.index === index);
    const channel = enabled ? numericValue('reference_channel') : 1;
    const sensitivity = enabled ? numericValue('reference_sensitivity_pa_per_fs') : null;
    if (enabled) {
      requireField('reference_device_index', Number.isInteger(index) && device?.approved_for_reference === true, 'Select an approved external reference input. Connect it and refresh inputs if needed.');
      requireField('reference_channel', Number.isInteger(channel) && channel >= 1 && channel <= device.max_input_channels, `Choose a reference channel from 1 to ${device.max_input_channels}.`);
      requireField('reference_sensitivity_pa_per_fs', sensitivity === null || sensitivity > 0, 'Reference sensitivity must be positive, or leave it unknown.');
    }
    return { enabled, device_index: index, device_name: enabled ? device.name : null, hostapi_name: enabled ? hostApiName(device) : null, channel, sample_rate_hz: 48000, microphone_model: textValue('reference_microphone_model'), microphone_serial: textValue('reference_microphone_serial'), interface_gain_note: textValue('reference_interface_gain_note'), placement_note: textValue('reference_placement_note'), distance_to_speaker_m: enabled ? numericValue('reference_distance_to_speaker_m') : null, calibration_file_path: textValue('reference_calibration_file_path'), sensitivity_pa_per_fs: sensitivity, calibration_record: textValue('reference_calibration_record') };
  }
  function runRequest(mode) {
    if (state.status.api_version !== 3) throw new Error('Open the updated v3 recorder before starting a take.');
    const invalid = Array.from(form.elements).find(control => !/^(calibrator_|reference_)/.test(control.name || '') && control.validity && !control.validity.valid);
    if (invalid) {
      reveal(invalid); invalid.reportValidity(); return null;
    }
    const setup = collectSetup();
    if (mode === 'measure') {
      requireField('speaker_connection', textValue('speaker_connection') === 'wired', 'Use wired playback for the KRK campaign and select Wired in speaker settings.');
      requireField('room_name', setup.room_name, 'Enter the room / table name.');
      requireField('position_name', setup.position_name, 'Enter the recorder position name.');
      requireField('source_distance_m', setup.source.distance_to_array_m > 0, 'Enter a speaker distance greater than zero metres.');
      requireField('source_angle_deg', setup.source.azimuth_lab_deg !== null && setup.source.azimuth_lab_deg >= -180 && setup.source.azimuth_lab_deg <= 180, 'Enter the speaker angle from −180° to 180°.');
      requireField('device_orientation', ['FLAT', 'UPRIGHT'].includes(setup.device.orientation), 'Choose Flat or Upright.');
    }
    const excitationId = textValue('excitation_id');
    const outputIndex = numericValue('playback_device_index');
    if (mode === 'measure') {
      requireField('playback_device_index', outputIndex !== null, 'Choose your speaker output in Setup.');
      requireField('excitation_id', excitationId, 'Choose an excitation file in Setup.');
    }
    const output = state.devices.find(device => device.index === outputIndex);
    const request = { schema_version: 3, mode, duration_seconds: numericValue('duration_seconds'), domain: textValue('domain'), playback_device_index: outputIndex, playback_device_name: output?.name ?? null, playback_channel: textValue('playback_channel'), excitation_id: mode === 'measure' ? excitationId : null, playback_gain_db: numericValue('playback_gain_db'), include_selected_angles: field('include_selected_angles').checked, setup, reference: { enabled: false } };
    if (request.duration_seconds === null) throw new Error('Enter the recording duration.');
    if (request.playback_gain_db === null) throw new Error('Enter a software playback level.');
    return request;
  }

  function renderControls() {
    $('delete-last-recording').disabled = !state.connected || state.initializing || state.busy || state.pending || archiveLoading || !latestDeletable;
    const canStart = state.connected && state.status.api_version === 3 && state.status.recovery?.ready !== false && !state.initializing && !state.busy && !state.pending;
    $('measure-button').disabled = !canStart;
    $('record-button').disabled = !canStart;
    $('inspect-devices').disabled = state.initializing || state.busy || state.pending;
    $('refresh-reference-devices').disabled = state.initializing || state.busy || state.pending;
    const reference = state.devices.find(device => String(device.index) === textValue('reference_device_index'));
    const distance = textValue('reference_distance_to_speaker_m');
    const speakerOutput = state.devices.find(device => String(device.index) === textValue('playback_device_index'));
    $('speaker-reference-button').disabled = !canStart || !field('reference_enabled').checked || reference?.approved_for_reference !== true || !speakerOutput || speakerOutput.max_output_channels < 1 || speakerOutput.approved_for_playback === false || textValue('speaker_connection') !== 'wired' || !textValue('excitation_id') || !textValue('reference_placement_note') || distance === null || !Number.isFinite(Number(distance)) || Number(distance) <= 0;
    const level = textValue('calibrator_known_spl_db'), frequency = textValue('calibrator_frequency_hz');
    $('calibrate-reference-button').disabled = !canStart || !field('reference_enabled').checked || reference?.approved_for_reference !== true || !field('calibrator_operator_confirmed').checked || level === null || !Number.isFinite(Number(level)) || frequency === null || !Number.isFinite(Number(frequency)) || Number(frequency) <= 0;
    $('stop-button').disabled = !state.connected || !state.busy || state.pending;
    $('load-profile').disabled = state.busy || state.pending;
    $('save-profile').disabled = !state.connected || state.pending;
  }
  function resetMetrics() {
    state.metricCache.clear(); state.telemetrySignature = ''; state.telemetrySeenAt = null;
    $('telemetry-values').replaceChildren();
    const empty = document.createElement('div'); empty.className = 'empty-state'; empty.textContent = 'Waiting for telemetry from this run.'; $('telemetry-values').append(empty);
    $('telemetry-raw').textContent = 'No data'; $('telemetry-age').textContent = 'No data';
  }
  async function startRun(mode) {
    if (state.busy || state.pending) return;
    let request;
    try { request = runRequest(mode); } catch (error) { notice(error.message, true); return; }
    if (!request) return;
    persist(); state.pending = true; renderControls(); notice('Submitting capture settings…');
    try {
      const result = await api('/api/run', request, 15000);
      if (result.accepted === false) throw new Error(result.message || 'The recorder did not accept this run.');
      state.busy = true; state.runId = result.run_id ?? null; state.resultSignature = ''; resetMetrics(); $('run-result').hidden = true;
      notice(request.domain === 'both' ? 'Starting two consecutive recordings. Keep the speaker and array still until both finish.' : 'Starting recording. Keep the speaker and array still until it finishes.');
    } catch (error) { notice(error.message, true); }
    finally { state.pending = false; renderControls(); await pollStatus(); }
  }
  async function stopRun() {
    state.pending = true; renderControls();
    try { await api('/api/stop', {}); notice('Stopping and saving the partial recording…'); }
    catch (error) { notice(error.message, true); }
    finally { state.pending = false; renderControls(); await pollStatus(); }
  }
  async function startReferenceCalibration() {
    if (!state.connected || state.status.api_version !== 3 || state.initializing || state.busy || state.pending) return;
    let request;
    try {
      const reference = collectReference();
      requireField('reference_enabled', reference.enabled, 'Enable and select the reference microphone first.');
      const level = numericValue('calibrator_known_spl_db'), frequency = numericValue('calibrator_frequency_hz');
      requireField('calibrator_known_spl_db', level !== null, 'Enter the calibrator’s stated level.');
      requireField('calibrator_frequency_hz', frequency !== null && frequency > 0, 'Enter the calibrator’s positive tone frequency.');
      requireField('calibrator_operator_confirmed', field('calibrator_operator_confirmed').checked, 'Confirm that the calibrator is fitted and its stated level and frequency are entered.');
      request = { schema_version: 3, reference, known_spl_db: level, frequency_hz: frequency, operator_confirmed: true };
    } catch (error) { notice(error.message, true); return; }
    state.pending = true; renderControls(); persist();
    try {
      const result = await api('/api/reference-calibration', request, 15000);
      if (result.accepted === false) throw new Error(result.message || 'The recorder did not accept the calibrator recording.');
      state.busy = true; state.runId = result.run_id ?? null; state.resultSignature = ''; $('run-result').hidden = true;
      field('calibrator_operator_confirmed').checked = false;
      notice('Recording the calibrator tone for 10 seconds. No speaker stimulus is played.');
    } catch (error) { notice(error.message, true); }
    finally { state.pending = false; renderControls(); await pollStatus(); }
  }
  function speakerReferenceRequest() {
    if (state.status.api_version !== 3) throw new Error('Open the updated v3 recorder before recording the speaker reference.');
    const reference = collectReference();
    requireField('reference_enabled', reference.enabled, 'Enable and select the setup reference input first.');
    requireField('reference_distance_to_speaker_m', reference.distance_to_speaker_m > 0, 'Enter a positive reference-to-speaker distance.');
    requireField('reference_placement_note', reference.placement_note, 'Describe the reference microphone position and orientation relative to the speaker.');
    const index = numericValue('playback_device_index');
    const output = state.devices.find(device => device.index === index);
    requireField('playback_device_index', Number.isInteger(index) && output?.max_output_channels > 0 && output.approved_for_playback !== false, 'Choose the explicit speaker output in Setup.');
    requireField('speaker_connection', textValue('speaker_connection') === 'wired', 'Use one wired speaker for the reference recording and select Wired in speaker settings.');
    const excitation = textValue('excitation_id');
    requireField('excitation_id', excitation, 'Choose an excitation file for the speaker reference.');
    const gain = numericValue('playback_gain_db');
    requireField('playback_gain_db', gain !== null && gain >= -60 && gain <= 0, 'Enter a fixed software playback level from −60 to 0 dB.');
    return { schema_version: 3, reference, excitation_id: excitation, playback_device_index: index, playback_device_name: output.name, playback_channel: textValue('playback_channel'), playback_gain_db: gain, setup: collectSetup() };
  }
  async function startSpeakerReference() {
    if (!state.connected || state.initializing || state.busy || state.pending) return;
    let request;
    try { request = speakerReferenceRequest(); } catch (error) { notice(error.message, true); return; }
    state.pending = true; renderControls(); persist();
    try {
      const result = await api('/api/speaker-reference', request, 15000);
      if (result.accepted === false) throw new Error(result.message || 'The recorder did not accept the speaker reference.');
      state.busy = true; state.runId = result.run_id ?? null; state.resultSignature = ''; $('run-result').hidden = true;
      notice('Playing the sweep and recording the setup reference microphone. Keep the speaker and reference microphone still.');
    } catch (error) { notice(error.message, true); }
    finally { state.pending = false; renderControls(); await pollStatus(); }
  }

  function displayValue(value) {
    if (value === null || value === undefined) return 'Unavailable';
    if (Array.isArray(value)) return value.map(displayValue).join('  ·  ');
    if (typeof value === 'number') return Number.isInteger(value) ? String(value) : Number(value.toPrecision(6)).toString();
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }
  function addMetricRow(command, value) {
    if (!Object.hasOwn(metricNames, command)) return;
    state.metricCache.set(command, value?.values ?? value?.value ?? value);
  }
  function ingestTelemetry(payload) {
    if (payload === null || payload === undefined) return;
    const signature = JSON.stringify(payload);
    if (signature !== state.telemetrySignature) { state.telemetrySignature = signature; state.telemetrySeenAt = Date.now(); }
    const visit = data => {
      if (Array.isArray(data)) { for (const item of data) if (item && typeof item === 'object') visit(item); return; }
      if (!data || typeof data !== 'object') return;
      if (data.command || data.name || data.field) addMetricRow(data.command || data.name || data.field, data.values ?? data.value ?? data.result ?? data);
      for (const [key, value] of Object.entries(data)) {
        addMetricRow(key, value);
        const aliases = { azimuths: 'AEC_AZIMUTH_VALUES', energies: 'AEC_SPENERGY_VALUES', selected_azimuths: 'AUDIO_MGR_SELECTED_AZIMUTHS' };
        if (aliases[key]) addMetricRow(aliases[key], value);
        if (key === 'readings' || key === 'metrics' || key === 'latest') visit(value);
      }
    };
    visit(payload);
    $('telemetry-raw').textContent = JSON.stringify(payload, null, 2);
    if (state.metricCache.size) {
      $('telemetry-values').replaceChildren();
      for (const command of Object.keys(metricNames)) {
        if (!state.metricCache.has(command)) continue;
        const row = document.createElement('div'); const title = document.createElement('dt'); const value = document.createElement('dd');
        title.textContent = metricNames[command]; value.textContent = displayValue(state.metricCache.get(command)); row.append(title, value); $('telemetry-values').append(row);
      }
    }
  }
  function appendReferenceResult(container, reference) {
    if (reference?.enabled !== true) return;
    const passed = reference.status === 'PASS' && reference.stream_closed === true;
    const text = document.createElement('small'); text.className = `reference-result${passed ? '' : ' warning'}`;
    text.textContent = `${passed ? 'Reference captured' : 'Reference failed'}${Number.isInteger(reference.frames) ? ` · ${reference.frames.toLocaleString()} frames` : ''}`;
    container.append(text);
  }
  function renderResult(result) {
    if (!result) return;
    const signature = JSON.stringify(result);
    if (signature === state.resultSignature) return;
    state.resultSignature = signature;
    const container = $('run-result'); container.replaceChildren(); container.hidden = false;
    const status = String(result.status || 'UNKNOWN').toUpperCase();
    const failed = Boolean(result.error) || result.success === false || ['FAIL', 'FAILED', 'ERROR', 'INVESTIGATE'].includes(status);
    const needsReview = ['REVIEW', 'RETAKE'].includes(status);
    const heading = document.createElement('div'); heading.className = 'result-heading';
    const title = document.createElement('strong');
    title.textContent = result.stopped ? 'Recording stopped' : result.kind === 'reference_calibration' && status === 'PASS' ? 'Calibrator recording saved' : result.kind === 'speaker_reference' && ['PASS', 'REVIEW'].includes(status) ? `Speaker reference saved${status === 'REVIEW' ? ' — review required' : ''}` : ({ PASS: 'Recording saved', REVIEW: 'Saved — review required', RETAKE: 'Please repeat this take', INVESTIGATE: 'Check this capture', ERROR: 'Recording error' }[status] || result.title || 'Latest take');
    const badge = document.createElement('span'); badge.className = `badge ${failed ? 'error' : needsReview ? 'busy' : status === 'PASS' ? 'good' : ''}`; badge.textContent = status;
    heading.append(title, badge); container.append(heading);
    if (result.run_id) { const id = document.createElement('div'); id.className = 'result-run-id'; id.textContent = result.run_id; container.append(id); }
    const markerStatus = result.acoustic_marker_review ?? result.quality?.acoustic_markers?.status;
    const message = document.createElement('div');
    message.textContent = result.stopped === true
      ? 'Recording stopped. Partial evidence was retained; this is not a completed measurement.'
      : failed
        ? result.message || `Capture checks failed: ${(result.failed_checks || []).join(', ') || result.error || 'inspect the run report'}.`
      : markerStatus === 'RETAKE'
        ? 'Acoustic marker checks failed. Repeat the measurement after checking the active speaker output, playback level and ambient sound.'
        : result.message || result.summary || 'Capture details are available below.';
    container.append(message);
    appendReferenceResult(container, result.reference);
    if (result.kind === 'reference_calibration' && status === 'PASS' && Number.isFinite(result.calibration?.pa_per_fs) && result.calibration.pa_per_fs > 0 && typeof result.calibration_record === 'string' && result.calibration_record) {
      const use = document.createElement('button'); use.type = 'button'; use.className = 'button secondary small'; use.textContent = 'Use this sensitivity';
      use.addEventListener('click', () => {
        field('reference_sensitivity_pa_per_fs').value = String(result.calibration.pa_per_fs);
        field('reference_calibration_record').value = result.calibration_record;
        persist(); updateSimpleUI();
        notice('Applied the recorded sensitivity to this reference setup. Keep the same microphone, input channel and interface gain.');
      });
      container.append(use);
    }
    if (typeof result.capture_integrity_pass === 'boolean') {
      const integrity = document.createElement('div'); integrity.className = 'result-integrity';
      integrity.textContent = `Digital capture integrity: ${result.capture_integrity_pass ? 'passed' : 'needs review'}.`;
      if (result.scientific_measurement_qualified === false) integrity.textContent += ' Scientific qualification is not established.';
      container.append(integrity);
    }
    if (Array.isArray(result.passes) && result.passes.length) {
      const passes = document.createElement('div'); passes.className = 'pass-list';
      for (const pass of result.passes) {
        const item = document.createElement('div'); item.className = 'pass-chip';
        const label = document.createElement('strong'); label.textContent = `${pass.domain === 'amplified' ? 'Amplified' : pass.domain === 'raw' ? 'Raw' : pass.domain} · ${pass.status || 'Unknown'}`;
        item.append(label);
        if (pass.message) { const text = document.createElement('small'); text.textContent = pass.message; item.append(text); }
        appendReferenceResult(item, pass.reference);
        if (typeof pass.report_url === 'string' && pass.report_url.startsWith('/runs/')) { const link = document.createElement('a'); link.href = pass.report_url; link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Report ↗'; item.append(link); }
        passes.append(item);
      }
      container.append(passes);
    }
    container.classList.toggle('error', failed);
    container.classList.toggle('warning', needsReview && !failed);
    if (typeof result.url === 'string') {
      try {
        const url = new URL(result.url, location.origin);
        if (url.origin === location.origin && ['http:', 'https:'].includes(url.protocol)) { const link = document.createElement('a'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Open run report / files ↗'; container.append(link); }
      } catch { /* Non-URL local paths remain visible in the raw result. */ }
    }
    const details = document.createElement('details'); const summary = document.createElement('summary'); summary.textContent = 'Full result'; const raw = document.createElement('pre'); raw.textContent = JSON.stringify(result, null, 2); details.append(summary, raw); container.append(details);
    if (archiveLoaded) loadRuns();
  }
  let statusInFlight = false;
  async function pollStatus() {
    if (statusInFlight) return;
    statusInFlight = true;
    try {
      const data = await api('/api/status', undefined, 5000);
      state.connected = true; state.busy = data.busy === true; state.status = data;
      const compatible = data.api_version === 3;
      $('connection-dot').className = `dot ${compatible ? 'online' : 'offline'}`; $('connection-label').textContent = compatible ? 'Recorder connected' : 'Recorder update needed';
      const rawLabel = typeof data.state === 'string' ? data.state.toLowerCase() : state.busy ? 'recording' : 'idle';
      const label = { idle: 'Ready', preflight: 'Getting ready', recording: 'Recording', restoring: 'Saving', analysing: 'Checking', analyzing: 'Checking', complete: 'Saved', error: 'Check capture', failed: 'Check capture' }[rawLabel] || rawLabel.replaceAll('_', ' ');
      $('state-badge').textContent = compatible ? label : 'Update needed'; $('state-badge').className = `badge ${!compatible || /error|failed/i.test(rawLabel) ? 'error' : state.busy ? 'busy' : 'good'}`;
      $('run-message').textContent = !compatible ? 'This page needs the v3 recorder. Open the updated launcher, then return here.' : data.message || (state.busy ? 'Recording is in progress. Keep this position unchanged.' : 'Ready when your speaker and array are in position.');
      if (data.recovery?.enabled && !data.recovery.ready) {
        $('connection-label').textContent = 'XVF reconnecting';
        $('state-badge').textContent = 'Waiting for XVF';
        $('state-badge').className = 'badge busy';
        $('run-message').textContent = data.recovery.message;
      }
      if (!state.initializing && !state.busy && !state.pending && data.recovery?.ready && recoveryGeneration !== data.recovery.generation) {
        state.pending = true; renderControls();
        try {
          await loadDevices(); persist(); restored = {};
          recoveryGeneration = data.recovery.generation;
          notice(data.recovery.message);
        } finally { state.pending = false; }
      }
      const suppliedProgress = data.progress?.percent ?? data.progress;
      let percent = typeof suppliedProgress === 'number' ? suppliedProgress : null;
      if (percent !== null && data.progress?.percent === undefined && percent >= 0 && percent <= 1) percent *= 100;
      if (percent !== null && Number.isFinite(percent)) { percent = Math.max(0, Math.min(100, percent)); $('progress-fill').style.width = `${percent}%`; $('progress-track').setAttribute('aria-valuenow', String(Math.round(percent))); }
      else { $('progress-fill').style.width = '0%'; $('progress-track').removeAttribute('aria-valuenow'); }
      $('progress-label').textContent = state.busy && percent !== null ? `${Math.round(percent)}%` : '';
      $('progress-track').classList.toggle('indeterminate', state.busy && percent === null);
      if (data.run_id && state.runId && data.run_id !== state.runId) resetMetrics();
      if (data.run_id) state.runId = data.run_id;
      ingestTelemetry(data.last_telemetry);
      if (state.telemetrySeenAt !== null) { const seconds = Math.floor((Date.now() - state.telemetrySeenAt) / 1000); $('telemetry-age').textContent = seconds < 2 ? 'Payload updated' : `Unchanged for ${seconds}s`; }
      if (data.device) {
        $('device-state').textContent = typeof data.device === 'string' ? data.device : JSON.stringify(data.device, null, 2);
        const gain = data.device.mic_gain ?? data.device.AEC_MIC_ARRAY_GAIN;
        if (gain !== undefined && gain !== null) $('mic-gain-readback').value = `${displayValue(gain)} × (readback)`;
        $('audio-format').replaceChildren();
        const formatRows = [
          ['Microphone sample rate', data.device.microphone_sample_rate_hz, ' Hz'],
          ['Packed USB carrier rate', data.device.native_sample_rate_hz, ' Hz'],
          ['USB input / output depth', data.device.usb_bit_depth, ' bits'],
          ['Preserved payload precision', data.device.payload_bits, ' bits'],
        ];
        for (const [label, value, units] of formatRows) {
          if (value === null || value === undefined) continue;
          const row = document.createElement('div'); const title = document.createElement('dt'); const content = document.createElement('dd');
          title.textContent = label; content.textContent = displayValue(value) + units; row.append(title, content); $('audio-format').append(row);
        }
      }
      if (!state.busy) renderResult(data.result);
    } catch (error) {
      state.connected = false;
      $('connection-dot').className = 'dot offline'; $('connection-label').textContent = 'Recorder unavailable';
      $('state-badge').textContent = 'Disconnected'; $('state-badge').className = 'badge error';
      $('run-message').textContent = `${error.message} Open the local recorder launcher to connect.`;
      $('progress-label').textContent = '';
      $('progress-track').classList.remove('indeterminate');
    } finally { statusInFlight = false; renderControls(); }
  }

  function replaceOptions(select, placeholder, entries, desired) {
    select.replaceChildren(new Option(placeholder, ''));
    for (const entry of entries) { const option = new Option(entry.label, String(entry.value)); option.disabled = entry.disabled === true; select.add(option); }
    if (desired !== null && desired !== undefined && entries.some(item => !item.disabled && String(item.value) === String(desired))) select.value = String(desired);
  }
  function recoveredPlaybackIndex(devices, selected, name, apiName) {
    if (!name) return selected;
    const matches = devices.filter(device => device.name === name && (!apiName || hostApiName(device) === apiName)
      && device.max_output_channels > 0 && device.approved_for_playback !== false);
    if (matches.some(device => String(device.index) === String(selected))) return selected;
    return apiName && matches.length === 1 ? String(matches[0].index) : null;
  }
  async function loadDevices(openDialog = false) {
    let selected = textValue('playback_device_index') ?? restored.playback_device_index;
    const priorName = state.devices.find(device => String(device.index) === String(selected))?.name ?? restored.playback_device_name;
    const priorApi = hostApiName(state.devices.find(device => String(device.index) === String(selected))) ?? restored.playback_hostapi_name;
    let referenceSelected = textValue('reference_device_index') ?? restored.reference_device_index;
    const priorReference = state.devices.find(device => String(device.index) === String(referenceSelected));
    const referenceFingerprint = priorReference ? { reference_device_name: priorReference.name, reference_hostapi_name: hostApiName(priorReference) } : restored;
    const data = await api('/api/devices', undefined, 20000);
    if (data.recovery?.enabled && !data.recovery.ready) return;
    state.devices = data.devices || [];
    selected = recoveredPlaybackIndex(state.devices, selected, priorName, priorApi);
    if (priorName && selected === null) {
      notice('The saved playback endpoint has changed. Select the current speaker output before measuring.', true);
    }
    const playbackChoices = state.devices.filter(device => {
      const apiName = device.hostapi_name ?? device.hostapi;
      const unsupportedAlias = /xvf|xmos/i.test(device.name) && typeof apiName === 'string' && !/WDM/i.test(apiName);
      const defaultMapper = /sound mapper|primary sound driver|default.*mapper/i.test(device.name);
      return device.max_output_channels > 0 && !unsupportedAlias && !defaultMapper && device.approved_for_playback !== false;
    });
    replaceOptions($('output-select'), 'Choose an output…', playbackChoices.map(device => {
      const apiName = device.hostapi_name ?? device.hostapi;
      return { value: device.index, label: `${device.name} · ${apiName} [${device.index}]` };
    }), selected);
    if (referenceSelected != null && String(referenceSelected) !== '' && !referenceDeviceMatches(state.devices.find(device => String(device.index) === String(referenceSelected)), referenceFingerprint)) {
      referenceSelected = null;
      notice('The saved setup reference input is unavailable or changed. Routine array recording remains available; reselect it only for another speaker reference.');
    }
    const referenceChoices = state.devices.filter(device => device.approved_for_reference === true && device.max_input_channels > 0);
    replaceOptions($('reference-input-select'), referenceChoices.length ? 'Choose an external input…' : 'No approved external inputs available', referenceChoices.map(device => ({ value: device.index, label: `${device.name} · ${hostApiName(device) ?? 'Unknown API'} · ${device.max_input_channels} channel(s) [${device.index}]` })), referenceSelected);
    outputDetail();
    $('devices-table').replaceChildren();
    for (const device of state.devices) {
      const row = document.createElement('tr');
      for (const value of [device.index, device.name, device.hostapi_name ?? device.hostapi, `${device.max_input_channels} / ${device.max_output_channels}`, device.default_samplerate == null ? 'Unknown' : `${device.default_samplerate} Hz`]) { const cell = document.createElement('td'); cell.textContent = String(value ?? 'Unknown'); row.append(cell); }
      $('devices-table').append(row);
    }
    if (!state.devices.length) { const row = document.createElement('tr'); const cell = document.createElement('td'); cell.colSpan = 5; cell.textContent = 'No audio devices reported.'; row.append(cell); $('devices-table').append(row); }
    if (openDialog) $('devices-dialog').showModal();
  }
  async function refreshDevices(openDialog = false) {
    if (state.initializing || state.busy || state.pending) return;
    state.pending = true; renderControls();
    try { await loadDevices(openDialog); persist(); }
    catch (error) { notice(error.message, true); }
    finally { state.pending = false; renderControls(); }
  }
  function excitationDetail() {
    const selected = state.excitations.find(excitation => String(excitation.id) === textValue('excitation_id'));
    $('excitation-detail').textContent = selected ? `${selected.label}${selected.duration_seconds == null ? '' : ` · ${selected.duration_seconds} seconds`}. The recorder saves the stimulus identity with the run. Record only does not play it.` : 'Measure plays the selected stimulus and records the array. Record only captures nearby phone audio, speech, or a quiet baseline without generated playback.';
  }
  function outputDetail() {
    const selected = state.devices.find(device => String(device.index) === textValue('playback_device_index'));
    const isXVF = selected && /xvf|xmos/i.test(selected.name);
    field('playback_channel').disabled = Boolean(isXVF);
    if (isXVF) field('playback_channel').value = 'left';
    $('output-route-note').textContent = isXVF
      ? 'XVF output: for a shared clock, wire XVF LINE OUT to ONE KRK GoAux 4 RCA input and verify only the intended cabinet plays. The default XVF DAC duplicates left onto both analog outputs, so software balance cannot isolate a cabinet on this route. Physical cabling has not been verified.'
      : selected
        ? 'Wired external output: left/right selects the playback channel. Playback and XVF capture use separate clocks; timing needs pilot verification. Confirm the active KRK cabinet and cable in Speaker settings; the EMM-6 reference step is optional.'
        : 'Choose an output to see its clock and routing notes. The software cannot verify the physical speaker cabling.';
    updateSimpleUI();
  }
  function updateSimpleUI() {
    $('obstruction-notes-field').hidden = !field('obstructed').checked;
    $('reference-fields').disabled = !field('reference_enabled').checked;
    const reference = state.devices.find(device => String(device.index) === textValue('reference_device_index'));
    if (reference?.approved_for_reference === true) field('reference_channel').max = String(reference.max_input_channels);
    else field('reference_channel').removeAttribute('max');
    $('reference-input-note').textContent = reference?.approved_for_reference === true ? `${reference.name} · ${hostApiName(reference)}. Choose input channel 1–${reference.max_input_channels}; recording stays at 48,000 Hz.` : 'Optional EMM-6: connect to an XLR microphone input with phantom power, then refresh and select that interface input. No input is selected automatically.';
    const rawAngle = textValue('source_angle_deg');
    const angle = rawAngle === null ? null : Number(rawAngle);
    const known = angle !== null && Number.isFinite(angle) && angle >= -180 && angle <= 180;
    $('diagram-source').toggleAttribute('hidden', !known);
    if (known) {
      const radians = angle * Math.PI / 180;
      const x = 175 - 74 * Math.sin(radians), y = 126 - 74 * Math.cos(radians);
      $('diagram-source-line').setAttribute('d', `M175 126L${x.toFixed(2)} ${y.toFixed(2)}`);
      $('diagram-source-dot').setAttribute('cx', x.toFixed(2)); $('diagram-source-dot').setAttribute('cy', y.toFixed(2));
    }
    const output = state.devices.find(device => String(device.index) === textValue('playback_device_index'));
    const domain = { both: 'Raw + amplified · two consecutive recordings', raw: 'Raw · one recording', amplified: 'Amplified · one recording' }[textValue('domain')];
    $('setup-summary').textContent = output ? `${domain}. ${textValue('speaker_model') || 'KRK GoAux 4'} · wired · fixed playback level ${textValue('playback_gain_db') ?? '?'} dB.` : `${domain}. Choose the wired KRK output in Setup. EMM-6 is optional.`;
    renderControls();
  }
  async function loadExcitations() {
    const selected = textValue('excitation_id') ?? restored.excitation_id;
    const data = await api('/api/excitations'); state.excitations = data.excitations || [];
    replaceOptions($('excitation-select'), state.excitations.length ? 'Choose an excitation…' : 'No excitation files available', state.excitations.map(excitation => ({ value: excitation.id, label: excitation.label })), selected);
    excitationDetail();
  }
  async function loadProfiles(selected = $('profile-select').value) {
    const data = await api('/api/profiles'); state.profiles = data.profiles || [];
    replaceOptions($('profile-select'), 'Choose a profile…', state.profiles.map(profile => ({ value: profile.id, label: profile.name })), selected);
  }
  async function loadRuns() {
    if (archiveLoading) return;
    archiveLoading = true; $('refresh-runs').disabled = true;
    try {
      const [data, deletion, annotations] = await Promise.all([api('/api/runs', undefined, 15000), api('/api/latest-recording'), api('/recording_reviews.json')]);
      latestDeletable = deletion.recording;
      $('delete-last-description').textContent = latestDeletable
        ? `Delete target: ${latestDeletable.id} · ${latestDeletable.room_name || 'Room unknown'} · ${latestDeletable.pose || 'Pose unknown'} · ${latestDeletable.distance_m ?? '?'} m / ${latestDeletable.angle_deg ?? '?'}°. One click moves it to the Recycle Bin.`
        : 'No recordings to delete.';
      const runs = data.runs || []; $('archive-rows').replaceChildren();
      $('archive-summary').textContent = runs.length ? `Latest ${Math.min(runs.length, 8)} saved takes. Open a report for checks and recording files.${data.read_errors?.length ? ' Some metadata could not be read; refresh to retry.' : ''}` : 'Your saved takes will appear here.';
      for (const run of runs.slice(0, 8)) {
        const row = document.createElement('tr'); const take = document.createElement('td');
        take.textContent = run.trial_label || run.id; const id = document.createElement('small'); id.textContent = run.id;
        const date = document.createElement('small'); date.textContent = run.recorded_utc ? new Date(run.recorded_utc).toLocaleString() : 'Time unknown'; take.append(id, date);
        const result = document.createElement('td'); result.textContent = run.domain || 'Domain unknown'; result.append(document.createElement('br'));
        const badge = document.createElement('span'); badge.className = `badge ${run.status === 'PASS' ? 'good' : ['REVIEW','RETAKE'].includes(run.status) ? 'busy' : 'error'}`; badge.textContent = run.status || 'UNKNOWN'; result.append(badge);
        // Bind annotations to the original timestamp as repeat IDs can be reused.
        const review = (annotations.runs || []).find(item => item.run_id === run.id && item.recorded_utc === run.recorded_utc);
        if (review?.background_noise_present === true) {
          const noise = document.createElement('small'); noise.textContent = 'Background noise present'; result.append(noise);
          const retained = document.createElement('small'); retained.textContent = 'Retained for later noise analysis; timing review still required.'; result.append(retained);
        }
        const locationCell = document.createElement('td'); locationCell.textContent = `${run.room_name || run.room_id || 'Room / table unknown'} / ${run.position_name || run.placement_id || 'Recorder position unknown'}`;
        const geometry = document.createElement('small'); geometry.textContent = `${run.distance_m == null ? 'Distance unknown' : run.distance_m + ' m'} · ${run.angle_deg == null ? 'Angle unknown' : run.angle_deg + '°'}`; locationCell.append(geometry);
        if (run.repeat_number != null) { const repeat = document.createElement('small'); repeat.textContent = `Repeat ${run.repeat_number}`; locationCell.append(repeat); }
        const pose = run.array_pose || {}; const poseCell = document.createElement('td'); poseCell.textContent = pose.orientation === 'FLAT' ? 'Flat' : pose.orientation === 'UPRIGHT' ? 'Upright' : 'Orientation unknown';
        const obstruction = document.createElement('small'); obstruction.textContent = run.obstruction === true ? 'Obstructed' : run.obstruction === false ? 'Unobstructed' : 'Obstruction unknown'; poseCell.append(obstruction);
        const files = document.createElement('td');
        for (const [label, path] of [['Report',run.report_url],['JSON',run.json_url]]) {
          if (typeof path !== 'string' || !path.startsWith('/runs/')) continue;
          const link = document.createElement('a'); link.href = path; link.target = '_blank'; link.rel = 'noopener'; link.textContent = label; files.append(link, document.createElement('br'));
        }
        if (review) {
          const link = document.createElement('a'); link.href = '/recording_reviews.json'; link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Noise review'; files.append(link);
        }
        row.append(take,result,locationCell,poseCell,files); $('archive-rows').append(row);
      }
      if (!runs.length) { const row = document.createElement('tr'); const cell = document.createElement('td'); cell.colSpan = 5; cell.textContent = 'Completed takes will appear here after evidence is saved.'; row.append(cell); $('archive-rows').append(row); }
      archiveLoaded = true;
    } catch (error) { latestDeletable = null; $('archive-summary').textContent = `Archive unavailable: ${error.message}`; }
    finally { archiveLoading = false; $('refresh-runs').disabled = false; renderControls(); }
  }
  async function deleteLastRecording() {
    if (state.busy || state.pending || archiveLoading || !latestDeletable) return;
    const target = latestDeletable;
    state.pending = true; latestDeletable = null; renderControls();
    try {
      const result = await api('/api/delete-last-recording', {run_id: target.id, token: target.token}, 65000);
      notice(result.message);
      if (state.runId === target.id) { state.runId = null; resetMetrics(); }
      state.resultSignature = ''; $('run-result').hidden = true;
    } catch (error) { notice(error.message, true); }
    finally { await loadRuns(); state.pending = false; await pollStatus(); renderControls(); }
  }
  async function saveProfile() {
    const name = $('profile-name').value.trim();
    if (!name) { notice('Enter a profile name before saving the setup.', true); $('profile-name').focus(); return; }
    try {
      const profile = await api('/api/profiles', { name, data: { ui_schema_version: 3, form: formSnapshot(), setup: collectSetup() } });
      await loadProfiles(profile.id ?? profile.profile?.id); persist(); notice(`Saved setup profile “${name}”.`);
    } catch (error) { notice(error.message, true); }
  }
  function loadProfile() {
    const profile = state.profiles.find(item => String(item.id) === $('profile-select').value);
    if (!profile) { notice('Choose a saved profile first.', true); return; }
    const snapshot = profile.data?.form;
    if (!snapshot || typeof snapshot !== 'object') { notice('This profile has no compatible form snapshot. Its saved data was not changed.', true); return; }
    applySnapshot(snapshot); $('profile-name').value = profile.name; persist(); notice(`Loaded setup profile “${profile.name}”. Check playback device selection before measuring.`);
  }

  form.addEventListener('submit', event => event.preventDefault());
  function resetCalibratorConfirmation(event) {
    if (['reference_enabled', 'reference_device_index', 'reference_channel', 'reference_interface_gain_note', 'reference_microphone_model', 'reference_microphone_serial', 'calibrator_known_spl_db', 'calibrator_frequency_hz'].includes(event.target.name)) field('calibrator_operator_confirmed').checked = false;
  }
  form.addEventListener('input', event => { resetCalibratorConfirmation(event); updateSimpleUI(); persist(); });
  form.addEventListener('change', event => { resetCalibratorConfirmation(event); outputDetail(); persist(); excitationDetail(); updateSimpleUI(); });
  $('profile-name').addEventListener('input', persist);
  $('measure-button').addEventListener('click', () => startRun('measure'));
  $('record-button').addEventListener('click', () => startRun('record'));
  $('stop-button').addEventListener('click', stopRun);
  $('save-profile').addEventListener('click', saveProfile);
  $('load-profile').addEventListener('click', loadProfile);
  $('inspect-devices').addEventListener('click', () => refreshDevices(true));
  $('refresh-reference-devices').addEventListener('click', () => refreshDevices());
  $('calibrate-reference-button').addEventListener('click', startReferenceCalibration);
  $('speaker-reference-button').addEventListener('click', startSpeakerReference);
  $('close-devices').addEventListener('click', () => $('devices-dialog').close());
  $('refresh-runs').addEventListener('click', loadRuns);
  $('delete-last-recording').addEventListener('click', deleteLastRecording);
  async function initialize() {
    renderControls();
    try {
      await pollStatus();
      const results = await Promise.allSettled([loadDevices(), loadExcitations(), loadProfiles(), loadRuns()]);
      const failures = results.filter(result => result.status === 'rejected').map(result => result.reason.message);
      if (failures.length) notice(failures.join(' '), true);
      // Device indices and excitation IDs are only restored if still present in the current inventory.
      if (state.status.recovery?.ready !== false) restored = {};
    } finally {
      state.initializing = false;
      renderControls();
    }
  }
  initialize();
  setInterval(pollStatus, 1000);
})();
