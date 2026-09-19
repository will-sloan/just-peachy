// Run real GUI request/migration functions against a small form fixture. No browser or audio.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const app = fs.readFileSync('measurement_app/static/app.js', 'utf8');
function sourceOf(name) {
  const start = app.indexOf(`  function ${name}(`);
  assert(start >= 0, name);
  const end = app.indexOf('\n  }', start) + 4;
  return app.slice(start, end);
}
const controls = new Map();
function field(name) {
  if (!controls.has(name)) controls.set(name, {name, value:'', checked:false, validity:{valid:true}});
  return controls.get(name);
}
const state = {status:{api_version:3},devices:[{index:7,name:'Wired KRK output',max_output_channels:2,approved_for_playback:true}]};
const context = {state, field, numberFields:['source_distance_m','source_angle_deg','os_volume_pct'],
  form:{get elements(){return [...controls.values()];}},
  textValue:name => String(field(name).value).trim() || null,
  numericValue:name => field(name).value === '' ? null : Number(field(name).value),
  requireField:(name,valid,message)=>{if(!valid)throw Error(message);},
  reveal:()=>{}, hostApiName:d=>d?.hostapi_name,
  $:id=>field(id)};
vm.createContext(context);
vm.runInContext(['migrateHardwareSnapshot','collectSetup','runRequest','formSnapshot'].map(sourceOf).join('\n'),context);
const normalize=value=>JSON.parse(JSON.stringify(value));
const old={speaker_model:'Edifier bt1800',speaker_volume_mark:'old dial',bass_dial:'old bass',playback_device_index:'9',
  reference_microphone_model:'Old reference',reference_calibration_file_path:'old.txt',reference_sensitivity_pa_per_fs:'42',
  source_distance_m:'1.25',source_angle_deg:'0',notes:'Prior source notes',domain:'amplified'};
const migrated=normalize(context.migrateHardwareSnapshot(old));
assert.equal(migrated.speaker_model,'KRK GoAux 4');
assert.equal(migrated.speaker_connection,'wired');
assert.equal(migrated.reference_microphone_model,'Dayton Audio EMM-6');
assert.equal(migrated.reference_enabled,false);
for(const name of ['speaker_volume_mark','bass_dial','playback_device_index','reference_calibration_file_path','reference_sensitivity_pa_per_fs'])assert.equal(migrated[name],'');
assert.equal(migrated.source_distance_m,'1.25');assert.equal(old.speaker_model,'Edifier bt1800');
assert.deepEqual(normalize(context.migrateHardwareSnapshot(migrated)),migrated);
const latest={...migrated,speaker_volume_mark:'new mark',speaker_arc_state:'on_fixed',speaker_interface_output_level:'interface 0 dB'};
assert.deepEqual(normalize(context.migrateHardwareSnapshot(latest)),latest);
for(const [name,value] of Object.entries({room_name:'Fixture room',position_name:'Fixture position',source_distance_m:'1.25',source_angle_deg:'0',device_orientation:'FLAT',speaker_model:'KRK GoAux 4',speaker_connection:'wired',speaker_arc_state:'off',speaker_arc_note:'Fixed before campaign',speaker_interface_output_level:'Interface 0 dB',speaker_orientation_note:'Facing marked arrow',bass_dial:'flat',treble_dial:'flat',os_volume_pct:'30',playback_device_index:'7',playback_gain_db:'-18',duration_seconds:'15',domain:'amplified',excitation_id:'fixture'}))field(name).value=value;
field('speaker_settings_fixed').checked=true;
// Stale, invalid optional-reference fields must not prevent a normal run.
field('reference_enabled').checked=true;
field('reference_device_index').value='unplugged';field('reference_device_index').validity.valid=false;
field('reference_calibration_file_path').value='missing-calibration-file.txt';
const request=normalize(context.runRequest('measure'));
assert.deepEqual(request.reference,{enabled:false});
assert.equal(request.domain,'amplified');
assert.equal(request.setup.speaker.arc_state_user_reported,'off');
assert.equal(request.setup.speaker.interface_output_level_user_note,'Interface 0 dB');
assert.equal(request.setup.speaker.orientation_user_note,'Facing marked arrow');
assert.equal(request.setup.speaker.eq_lf,'flat');assert.equal(request.setup.speaker.os_volume_pct,30);
assert.equal(request.setup.calibration.source_correction_applied,false);
assert.equal(request.setup.calibration.reference_optional,true);
assert.deepEqual(request.setup.hardware_context.primary_rir_channels,['MIC0','MIC1','MIC2','MIC3']);
const snapshot=normalize(context.formSnapshot());
assert.equal(snapshot.speaker_arc_state,'off');assert.equal(snapshot.hardware_context_version,'krk-emm6-2026-09-06');
field('speaker_connection').value='bluetooth';
assert.throws(()=>context.runRequest('measure'),/wired/i);
console.log('PASS: hardware migration, stale-setting reset, idempotence, geometry preservation, metadata, optional-reference independence, profile snapshot and wired-only request contracts.');
