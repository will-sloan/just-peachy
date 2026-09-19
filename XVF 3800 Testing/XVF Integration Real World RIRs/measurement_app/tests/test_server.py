"""Loopback HTTP contract tests with every hardware entry point replaced.

The fixture imports an isolated server instance after redirecting BASE/RUNS,
profiles and its Windows lock file into one verified temporary directory.
It never starts the production server or touches the connected board.
"""
import http.client
import importlib.util
import io
import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from measurement_app import acquisition, core


class HTTPContractTests(unittest.TestCase):
    def setUp(self):
        self.workspace = core.BASE.resolve()
        self.tmp_root = (self.workspace / 'tmp').resolve()
        self.tmp_root.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='measurement_http_test_', dir=self.tmp_root)
        self.base = Path(self.temporary.name).resolve()
        self.assertTrue(self.base.is_relative_to(self.tmp_root))
        (self.base / 'measurement_app' / 'static').mkdir(parents=True)
        (self.base / 'runs').mkdir()
        (self.base / 'measurement_app' / 'static' / 'index.html').write_text('<!doctype html><title>HTTP test fixture</title>', encoding='utf-8')
        (self.base / 'private.txt').write_text('private fixture sentinel', encoding='utf-8')
        spec = importlib.util.spec_from_file_location('measurement_app._isolated_http_test_server', self.workspace / 'measurement_app' / 'server.py')
        self.server = importlib.util.module_from_spec(spec)
        with patch.object(core, 'BASE', self.base), patch.object(core, 'RUNS', self.base / 'runs'):
            spec.loader.exec_module(self.server)
        # The server module looks up these symbols at call time. Defaults forbid
        # acquisition/control; tests that need a run replace acquire with a fixture.
        self.server.Control = Mock(side_effect=AssertionError('Real control forbidden in HTTP tests'))
        self.server.inspect = Mock(return_value=None)
        self.server.devices = Mock(return_value=[])
        self.server.acquire = Mock(side_effect=AssertionError('Real acquisition forbidden in HTTP tests'))
        self.server.list_excitations = Mock(return_value=[])
        self.httpd = self.server.ThreadingHTTPServer(('127.0.0.1', 0), self.server.Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.server.PORT = self.port
        self.serve_thread = threading.Thread(target=self.httpd.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
        self.serve_thread.start()
        self.run_release = threading.Event()

    def tearDown(self):
        self.run_release.set()
        self.server.STOP.set()
        deadline = time.monotonic() + 3
        while self.server.STATE['busy'] and time.monotonic() < deadline:
            time.sleep(.01)
        self.httpd.shutdown()
        self.httpd.server_close()
        self.serve_thread.join(2)
        self.server.LEASE.close()
        self.assertTrue(self.base.is_relative_to(self.tmp_root))
        self.temporary.cleanup()

    def test_delete_route_refuses_active_recording(self):
        self.server.STATE['busy'] = True
        try:
            with patch.object(self.server, 'recycle_latest') as recycle:
                status, body = self.request('POST', '/api/delete-last-recording', {'run_id': 'x', 'token': 'x'})
                self.assertEqual(status, 409)
                recycle.assert_not_called()
        finally:
            self.server.STATE['busy'] = False

    def test_delete_route_clears_deleted_result_and_releases_lease(self):
        self.server.STATE['result'] = {'run_id': 'JPXVF_fixture'}
        with patch.object(self.server, 'recycle_latest', return_value={'id':'JPXVF_fixture','deleted':True,'message':'Recycled fixture'}) as recycle:
            status, body = self.request('POST', '/api/delete-last-recording', {'run_id':'JPXVF_fixture','token':'expected'})
            self.assertEqual(status, 200)
            recycle.assert_called_once_with(self.server.RUNS, 'JPXVF_fixture', 'expected')
            self.assertIsNone(self.server.STATE['result'])
            self.assertFalse(self.server.STATE['busy'])

    def test_recovery_pending_does_not_reserve_or_start_a_take(self):
        self.server.RECOVERY = Mock(ready=False, inventory=[])
        status, body = self.request('POST', '/api/run', {'schema_version': 3})
        self.assertEqual(status, 409)
        self.assertIn('recovery', body['error'])
        self.assertEqual(list((self.base / 'runs').iterdir()), [])
        self.server.acquire.assert_not_called()

    def request(self, method, path, data=None, *, raw=None, origin=None, host=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        body = raw if raw is not None else json.dumps(data) if data is not None else None
        headers = {'Host': host or f'127.0.0.1:{self.port}'}
        if method == 'POST':
            headers['Content-Type'] = 'application/json'
        if origin is not None:
            headers['Origin'] = origin
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        status = response.status
        content_type = response.getheader('Content-Type') or ''
        connection.close()
        return status, json.loads(payload) if 'application/json' in content_type else payload

    def test_invalid_json_and_nonfinite_numeric_forms_rejected_without_writes(self):
        bodies = ['{"name":', '{"name":"bad","data":{"distance":NaN}}', '{"name":"bad","data":{"distance":Infinity}}', '{"name":"bad","data":{"distance":1e309}}']
        for body in bodies:
            with self.subTest(body=body):
                status, _ = self.request('POST', '/api/profiles', raw=body)
                self.assertEqual(status, 400)
        self.assertEqual(list(self.server.PROFILES.glob('*.json')), [])
        self.server.acquire.assert_not_called()
        self.server.inspect.assert_not_called()

    def test_nonobject_request_body_is_a_client_error(self):
        for raw in ['[]', 'null', '"string"', '1']:
            with self.subTest(raw=raw):
                status, _ = self.request('POST', '/api/profiles', raw=raw)
                self.assertEqual(status, 400)

    def test_profile_preserves_unknown_nulls_and_provenance_exactly(self):
        data = {'ui_schema_version': 1, 'form': {'source_distance_m': '', 'device_yaw_deg': ''}, 'setup': {'source': {'distance_to_array_m': None}, 'device': {'yaw_deg': None}, 'metadata_provenance': {'source_distance_m': 'unknown', 'device_yaw_deg': 'unknown'}}}
        status, saved = self.request('POST', '/api/profiles', {'name': 'Unknown geometry fixture', 'data': data}, origin=f'http://127.0.0.1:{self.port}')
        self.assertEqual(status, 201)
        self.assertEqual(saved['data'], data)
        status, listed = self.request('GET', '/api/profiles')
        self.assertEqual(status, 200)
        self.assertEqual(listed['profiles'][0]['data'], data)
        self.assertEqual(len(list(self.server.PROFILES.glob('*.json'))), 1)
        self.server.acquire.assert_not_called()
        self.server.inspect.assert_not_called()

    def test_foreign_origin_and_host_cannot_write(self):
        status, _ = self.request('POST', '/api/profiles', {'name': 'Foreign', 'data': {}}, origin='https://example.org')
        self.assertEqual(status, 403)
        status, _ = self.request('POST', '/api/profiles', {'name': 'Foreign', 'data': {}}, host='example.org')
        self.assertEqual(status, 403)
        self.assertEqual(list(self.server.PROFILES.glob('*.json')), [])

    def test_encoded_path_traversal_does_not_read_private_files(self):
        paths = ['/%2e%2e/%2e%2e/private.txt', '/%2e%2e%5c%2e%2e%5cprivate.txt', '/runs/%2e%2e/private.txt', '/runs/%2e%2e%5cprivate.txt']
        for path in paths:
            with self.subTest(path=path):
                status, data = self.request('GET', path)
                self.assertEqual(status, 404)
                self.assertNotIn('private fixture sentinel', str(data))

    def test_status_keeps_metric_rows_separate_and_nonfinite_values_null(self):
        self.server.update(last_telemetry={'command': 'AEC_AZIMUTH_VALUES', 'values': [1.1, None, 2.2, 3.3], 'units': 'radians'})
        self.server.update(last_telemetry={'command': 'AEC_SPENERGY_VALUES', 'values': [4, 5, 6, 7], 'units': 'vendor_speech_energy_units'})
        self.server.update(device={'microphone_sample_rate_hz': 16000, 'native_sample_rate_hz': 48000, 'payload_bits': 23, 'usb_bit_depth': [24, 24], 'mic_gain': 10})
        status, data = self.request('GET', '/api/status')
        self.assertEqual(status, 200)
        self.assertEqual(set(data['last_telemetry']), {'AEC_AZIMUTH_VALUES', 'AEC_SPENERGY_VALUES'})
        self.assertIsNone(data['last_telemetry']['AEC_AZIMUTH_VALUES']['values'][1])
        self.assertEqual(data['device']['payload_bits'], 23)
        self.server.inspect.assert_not_called()

    def test_run_archive_preserves_unknown_pose_and_reads_only_completed_evidence(self):
        folder=self.server.RUNS/'TAKE_20260905T223303_130671Z_fixture';folder.mkdir()
        request={'domain':'raw','setup':{'trial_label':'front repeat','room_id':'R1','placement_id':'P2','device':{'orientation':'FLAT','yaw_deg':None,'pitch_deg':0}}}
        core.write_json(folder/'request.json',request);core.write_json(folder/'result.json',{'status':'RETAKE'})
        (folder/'SHA256SUMS.txt').write_text('fixture manifest presence only',encoding='utf-8')
        before={p.name:core.sha(p) for p in folder.iterdir()}
        incomplete=self.server.RUNS/'TAKE_incomplete';incomplete.mkdir();core.write_json(incomplete/'request.json',request)
        status,data=self.request('GET','/api/runs')
        self.assertEqual(status,200);self.assertEqual(len(data['runs']),1)
        row=data['runs'][0];self.assertEqual(row['status'],'RETAKE');self.assertEqual(row['trial_label'],'front repeat')
        self.assertIsNone(row['array_pose']['yaw_deg']);self.assertEqual(row['array_pose']['pitch_deg'],0)
        self.assertFalse(row['manifest_verified_by_listing']);self.assertTrue(row['manifest_present'])
        self.assertEqual(before,{p.name:core.sha(p) for p in folder.iterdir()})
        self.server.inspect.assert_not_called();self.server.devices.assert_not_called();self.server.acquire.assert_not_called()

    def test_device_discovery_and_run_validation_share_endpoint_policy(self):
        endpoints = [
            {'index': 1, 'name': 'Speakers (Realtek(R) Audio)', 'hostapi_name': 'Windows WASAPI', 'max_input_channels': 0, 'max_output_channels': 2},
            {'index': 2, 'name': 'Output (XVF3800 Voice Processor)', 'hostapi_name': 'Windows WDM-KS', 'max_input_channels': 0, 'max_output_channels': 2},
            {'index': 3, 'name': 'Echo Cancelling Speakerphone (X', 'hostapi_name': 'MME', 'max_input_channels': 0, 'max_output_channels': 2},
            {'index': 4, 'name': 'Microsoft Sound Mapper - Output', 'hostapi_name': 'MME', 'max_input_channels': 0, 'max_output_channels': 2},
            {'index': 5, 'name': 'Input (XVF3800 Voice Processor)', 'hostapi_name': 'Windows WDM-KS', 'max_input_channels': 2, 'max_output_channels': 0},
            {'index': 6, 'name': 'Primary Sound Driver', 'hostapi_name': 'Windows DirectSound', 'max_input_channels': 0, 'max_output_channels': 2},
        ]
        self.server.devices = Mock(return_value=endpoints)
        status, body = self.request('GET', '/api/devices')
        self.assertEqual(status, 200)
        self.assertEqual({device['index'] for device in body['devices']}, {1, 2, 5})
        self.assertEqual({device['index'] for device in body['devices'] if device['approved_for_playback']}, {1, 2})
        with patch.object(acquisition, 'devices', return_value=endpoints), patch.object(acquisition, 'get_excitation', return_value={'id': 'fixture'}):
            for index in [3, 4, 6]:
                with self.subTest(index=index):
                    status, _ = self.request('POST', '/api/run', {'schema_version':3,'mode': 'measure', 'excitation_id': 'fixture', 'playback_device_index': index,'setup':{'room_name':'Fixture room','position_name':'Fixture position','source':{'distance_to_array_m':1,'azimuth_lab_deg':0},'device':{'orientation':'FLAT'},'obstruction':{'present':False}}})
                    self.assertEqual(status, 400)
        self.server.acquire.assert_not_called()
        self.assertFalse(self.server.STATE['busy'])

    def test_required_metadata_fails_before_inventory_or_reservation(self):
        with patch.object(acquisition,'devices',side_effect=AssertionError('Inventory forbidden')):
            code,_=self.request('POST','/api/run',{'schema_version':3,'mode':'measure','setup':{}})
        self.assertEqual(code,400)
        self.assertEqual(list(self.server.RUNS.iterdir()),[])
        self.assertFalse(self.server.STATE['busy'])

    def test_normal_run_rejects_reference_before_inventory_or_reservation(self):
        with patch.object(self.server,'validate_request',side_effect=AssertionError('Validation must not open reference device')):
            code,data=self.request('POST','/api/run',{'schema_version':3,'mode':'record','reference':{'enabled':True}})
        self.assertEqual(code,400)
        self.assertIn('separate one-time',data['error'])
        self.assertFalse(self.server.STATE['busy'])
        self.assertEqual(list(self.server.RUNS.iterdir()),[])

    def test_reference_routes_dispatch_only_their_own_worker_and_freeze_archive(self):
        for endpoint,mode,prefix,attribute,validator in [
            ('/api/speaker-reference','speaker_reference','SPEAKER_REF_','acquire_speaker_reference','validate_speaker_reference'),
            ('/api/reference-calibration','reference_calibration','REFERENCE_CAL_','acquire_calibration','validate_calibration_request')]:
            with self.subTest(mode=mode):
                request={'schema_version':3,'mode':mode,'domain':'reference','setup':{}}
                def fake_capture(req,folder,stop,update):
                    self.assertEqual(req['mode'],mode)
                    core.write_json(folder/'request.json',req)
                    result={'kind':mode,'run_id':folder.name,'status':'REVIEW','message':'Offline reference fixture'}
                    core.write_json(folder/'result.json',result)
                    (folder/'REPORT.txt').write_text('offline fixture')
                    core.freeze(folder)
                    return result
                with patch.object(self.server,validator,return_value=request), patch.object(self.server,attribute,side_effect=fake_capture) as capture:
                    code,data=self.request('POST',endpoint,request)
                    self.assertEqual(code,202);self.assertTrue(data['run_id'].startswith(prefix))
                    deadline=time.monotonic()+2
                    while self.server.STATE['busy'] and time.monotonic()<deadline:time.sleep(.01)
                    capture.assert_called_once()
                    self.assertFalse(self.server.STATE['busy'])
                    self.assertEqual(self.server.STATE['result']['kind'],mode)
                    self.assertEqual(self.server.STATE['result']['status'],'REVIEW')
        code,archive=self.request('GET','/api/runs')
        self.assertEqual(code,200);self.assertEqual(len(archive['runs']),2)
        self.server.acquire.assert_not_called();self.server.inspect.assert_not_called()

    def test_old_backend_is_recognized_but_never_reused(self):
        state={**self.server.STATE,'api_version':2}
        identity,requests=self.probe_fixture(state)
        self.assertEqual(identity['identification'],'incompatible_version')
        with patch.object(self.server,'identify_existing_instance',return_value=identity), patch.object(self.server.webbrowser,'open') as browser:
            with self.assertRaisesRegex(RuntimeError,'older recorder'):
                self.server.reuse_existing_instance(self.port,True)
            browser.assert_not_called()

    def probe_fixture(self, status, title='<title>Just Peachy · XVF Measurement</title>', response_status=200):
        requests = []
        def connection(host, port, timeout):
            self.assertEqual(host, '127.0.0.1')
            self.assertEqual(port, self.port)
            client = MagicMock()
            target = [None]
            def request(method, path, **kwargs):
                self.assertEqual(method, 'GET')
                self.assertIn(path, ['/api/status', '/'])
                target[0] = path
                requests.append(path)
            def response():
                result = MagicMock()
                result.status = response_status
                result.read.return_value = (json.dumps(status) if target[0] == '/api/status' else title).encode('utf-8')
                return result
            client.request.side_effect = request
            client.getresponse.side_effect = response
            return client
        with patch.object(self.server.http.client, 'HTTPConnection', side_effect=connection):
            result = self.server.identify_existing_instance(self.port)
        return result, requests

    def test_launcher_identifies_current_app_without_board_or_title_probe(self):
        result, requests = self.probe_fixture(dict(self.server.STATE))
        self.assertEqual(result['identification'], 'app_id')
        self.assertEqual(requests, ['/api/status'])
        self.server.inspect.assert_not_called()
        self.server.devices.assert_not_called()

    def test_launcher_legacy_identity_requires_status_device_and_exact_title(self):
        status = dict(self.server.STATE)
        status.pop('app_id')
        status.pop('api_version')
        status['device'] = {'version': '3.2.1', 'build': 'ua-io48-lin', 'native_sample_rate_hz': 48000, 'microphone_sample_rate_hz': 16000, 'usb_bit_depth': [24, 24], 'payload_bits': 23}
        result, requests = self.probe_fixture(status)
        self.assertEqual(result['identification'], 'legacy_status_and_title')
        self.assertEqual(requests, ['/api/status', '/'])
        self.assertIsNone(self.probe_fixture(status, title='<title>Another local app</title>')[0])
        status['device'] = {**status['device'], 'payload_bits': 24}
        self.assertIsNone(self.probe_fixture(status)[0])
        self.server.inspect.assert_not_called()
        self.server.devices.assert_not_called()

    def test_launcher_rejects_foreign_identity_redirect_and_connection_failure(self):
        status = {**self.server.STATE, 'app_id': 'another-app'}
        self.assertIsNone(self.probe_fixture(status)[0])
        self.assertIsNone(self.probe_fixture(dict(self.server.STATE), response_status=302)[0])
        with patch.object(self.server.http.client, 'HTTPConnection', side_effect=OSError('not listening')):
            self.assertIsNone(self.server.identify_existing_instance(self.port))

    def test_launcher_reuses_existing_app_and_exits_without_binding(self):
        identity = {'url': 'http://127.0.0.1:8767', 'identification': 'app_id'}
        with patch.object(self.server, 'identify_existing_instance', return_value=identity) as identify, \
             patch.object(self.server, 'ThreadingHTTPServer') as listener, \
             patch.object(self.server.webbrowser, 'open') as browser, \
             patch.object(self.server.sys, 'argv', ['server', '--open-browser']), redirect_stdout(io.StringIO()):
            self.assertEqual(self.server.main(), 0)
            identify.assert_called_once_with(8767)
            listener.assert_not_called()
            browser.assert_called_once_with(identity['url'])
        self.server.acquire.assert_not_called()

    def test_launcher_occupied_foreign_port_fails_without_opening_or_killing(self):
        with patch.object(self.server, 'identify_existing_instance', return_value=None), \
             patch.object(self.server, 'ThreadingHTTPServer', side_effect=OSError('occupied')), \
             patch.object(self.server.webbrowser, 'open') as browser, \
             patch.object(self.server.sys, 'argv', ['server', '--open-browser']), redirect_stderr(io.StringIO()):
            self.assertEqual(self.server.main(), 1)
            browser.assert_not_called()
        self.server.acquire.assert_not_called()

    def test_launcher_bind_race_reuses_the_newly_identified_app(self):
        identity = {'url': 'http://127.0.0.1:8767', 'identification': 'app_id'}
        with patch.object(self.server, 'identify_existing_instance', side_effect=[None, identity]), \
             patch.object(self.server, 'ThreadingHTTPServer', side_effect=OSError('bind race')), \
             patch.object(self.server.webbrowser, 'open') as browser, \
             patch.object(self.server.sys, 'argv', ['server', '--open-browser']), redirect_stdout(io.StringIO()):
            self.assertEqual(self.server.main(), 0)
            browser.assert_called_once_with(identity['url'])

    def test_completed_worker_preserves_marker_retake_despite_digital_pass(self):
        self.server.acquire = Mock(return_value={
            'run_id': 'fixture_marker_failure', 'status': 'RETAKE',
            'capture_integrity_pass': True, 'acoustic_marker_review': 'RETAKE',
            'scientific_measurement_qualified': False,
            'message': 'Acoustic marker checks failed; repeat the measurement.',
        })
        status, _ = self.request('POST', '/api/run', {'schema_version':3,'mode': 'record', 'duration_seconds': 5, 'setup': {}})
        self.assertEqual(status, 202)
        deadline = time.monotonic() + 2
        while self.server.STATE['busy'] and time.monotonic() < deadline:
            time.sleep(.01)
        status, state = self.request('GET', '/api/status')
        self.assertEqual(status, 200)
        self.assertEqual(state['state'], 'complete')
        # "complete" describes worker lifetime; the result exposed to the UI
        # must retain RETAKE and may not be upgraded by successful digital QC.
        self.assertEqual(state['result']['status'], 'RETAKE')
        self.assertEqual(state['result']['passes'][0]['acoustic_marker_review'], 'RETAKE')
        self.assertFalse(state['result']['capture_integrity_pass'])
        self.assertTrue(state['result']['passes'][0]['capture_integrity_pass'])
        self.assertFalse(state['result']['scientific_measurement_qualified'])
        self.assertIn('marker checks failed', state['message'])

    def test_simultaneous_runs_have_one_owner_and_one_take(self):
        acquired = threading.Event()
        def fake_acquire(request, folder, stop, update):
            folder.mkdir(parents=True, exist_ok=False)
            (folder / 'fixture.txt').write_text('one accepted worker', encoding='utf-8')
            acquired.set()
            if not self.run_release.wait(3):
                raise RuntimeError('Test worker release timed out')
            return {'run_id': folder.name, 'message': 'Fixture finished', 'status': 'PASS', 'scientific_measurement_qualified': False,'capture_integrity_pass':True}
        self.server.acquire = Mock(side_effect=fake_acquire)
        request = {'schema_version':3,'mode': 'record', 'duration_seconds': 5, 'domain': 'raw', 'setup': {'distance_m': None}}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.request, 'POST', '/api/run', request) for _ in range(2)]
            replies = [future.result() for future in futures]
        self.assertEqual(sorted(status for status, _ in replies), [202, 409])
        self.assertTrue(acquired.wait(1))
        self.assertTrue(self.server.STATE['busy'])
        self.assertEqual(self.server.acquire.call_count, 1)
        self.assertEqual(len(list(self.server.RUNS.glob('TAKE_*'))), 1)
        self.server.inspect.assert_not_called()
        self.server.devices.assert_not_called()
        self.run_release.set()


if __name__ == '__main__':
    unittest.main()
