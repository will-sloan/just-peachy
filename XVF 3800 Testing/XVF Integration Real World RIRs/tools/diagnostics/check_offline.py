"""Check local GUI startup/assets with non-loopback Python networking denied.

Does not change Windows networking, command the board, or play/record audio.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def local_network_only(event, args):
    if event == 'socket.connect':
        address = args[1]
        if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1'):
            raise RuntimeError('Offline check blocked non-loopback connection: ' + repr(address))
    if event == 'socket.getaddrinfo' and args[0] not in ('127.0.0.1', '::1', 'localhost', None):
        raise RuntimeError('Offline check blocked external DNS: ' + repr(args[0]))

sys.addaudithook(local_network_only)

import http.client
import json
import socket
import threading
from measurement_app import server
from measurement_app.core import HOST, devices
from measurement_app.excitation import ensure_assets

def main():
    try:
        with socket.socket() as probe:
            probe.connect(('192.0.2.1', 443))
    except RuntimeError:
        pass
    else:
        raise AssertionError('Network guard did not block external connection')

    # Read packaged control libraries and hash-check every excitation file.
    for name in ('xvf_host.exe', 'device_usb.dll', 'command_map.dll'):
        assert (HOST.parent / name).read_bytes(), name
    manifest = ensure_assets()
    inventory = devices()  # Local PortAudio enumeration only; no streams opened.
    assert not any(token in (ROOT / 'measurement_app/static' / name).read_text(encoding='utf-8')
                   for name in ('index.html', 'app.js', 'style.css')
                   for token in ('https://', 'http://', '@import', 'wss://'))
    service = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    server.PORT = service.server_port
    worker = threading.Thread(target=service.serve_forever, daemon=True)
    worker.start()
    receipts = {}
    try:
        for path in ('/', '/app.js', '/style.css', '/api/status', '/api/profiles',
                     '/api/excitations', '/guide', '/reference-guide'):
            connection = http.client.HTTPConnection('127.0.0.1', server.PORT, timeout=15)
            try:
                connection.request('GET', path)
                response = connection.getresponse()
                payload = response.read()
                assert response.status == 200 and payload, (path, response.status)
                receipts[path] = len(payload)
            finally:
                connection.close()
    finally:
        service.shutdown()
        service.server_close()
        worker.join(5)
    print(json.dumps({'status': 'PASS', 'external_python_network': 'denied',
                      'local_routes_bytes': receipts, 'verified_excitation_files': len(manifest['files']),
                      'local_audio_endpoints': len(inventory),
                      'scope': 'Fresh server, local dependencies/assets/guides/profiles; no physical recording or OS-wide network disconnection'}, indent=2))

if __name__ == '__main__':
    main()
