#!/usr/bin/env python3
"""Headless runtime checks. Run in an isolated network namespace with loopback up."""
import os
import sys
import traceback
import base64
import http.client
import gzip
import json
import secrets
import ipaddress
import platform
import re
import signal
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

host = '127.0.0.1'
port = 18743
origin = f'http://{host}:{port}'
user = 'kv-regression'
password = secrets.token_urlsafe(24)
auth = 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()
marker = 'KV-PRIVATE-INPUT-' + secrets.token_hex(12)


def Request(path, method='GET', credentials=auth, requestOrigin=None, body=None):

    headers = {}
    if credentials is not None:
        headers['Authorization'] = credentials
    if requestOrigin is not None:
        headers['Origin'] = requestOrigin
    if body is not None:
        headers['Content-Type'] = 'application/json'
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path, body, headers)
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def Upgrade(credentials, requestOrigin):

    client = socket.create_connection((host, port), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    headers = [
        'GET /ws/input HTTP/1.1', f'Host: {host}:{port}', 'Upgrade: websocket',
        'Connection: Upgrade', f'Sec-WebSocket-Key: {key}', 'Sec-WebSocket-Version: 13',
        f'Origin: {requestOrigin}'
    ]
    if credentials is not None:
        headers.append(f'Authorization: {credentials}')
    client.sendall(('\r\n'.join(headers) + '\r\n\r\n').encode())
    response = bytearray()
    while not response.endswith(b'\r\n\r\n'):
        data = client.recv(1)
        if not data:
            raise RuntimeError('Incomplete WebSocket handshake')
        response.extend(data)
    return client, int(response.split(b' ', 2)[1])


def SendText(client, text):

    payload = json.dumps({'type': 'text', 'text': text}).encode()
    assert len(payload) < 126
    mask = os.urandom(4)
    client.sendall(bytes([0x81, 0x80 | len(payload)]) + mask +
                   bytes(value ^ mask[i % 4] for i, value in enumerate(payload)))


def RunTests(binary):

    with tempfile.TemporaryDirectory() as work:
        env = os.environ.copy()
        env.pop('KV_USER', None)
        env.pop('KV_PASSWORD', None)
        failed = subprocess.run([binary, '-p', str(port)], env=env, cwd=work,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=5)
        assert failed.returncode != 0, 'Missing credentials accepted'
        env.update(KV_USER=user, KV_PASSWORD=password, LOG_LEVEL='debug')
        logPath = Path(work) / 'kv.log'
        tracePath = Path(work) / 'network.trace'
        with logPath.open('wb') as log:
            process = subprocess.Popen(['strace', '-f', '-qq', '-e', 'trace=connect,sendto,sendmsg',
                                        '-o', str(tracePath), binary, '-p', str(port), '--hotplug-interval=1'],
                                       env=env, cwd=work, stdout=log, stderr=log, start_new_session=True)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('KV exited during startup')
                    try:
                        if Request('/health')[0] == 200:
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError('KV did not start')
                for path in ('/', '/mobile', '/api/status', '/video.mjpg', '/audio.ogg'):
                    assert Request(path, credentials=None)[0] == 401, path
                    # A successful request resets the IP-based failure counter.
                    assert Request('/health')[0] == 200
                for path in ('/', '/mobile', '/vendor/pico.min.css', '/vendor/fonts.css',
                             '/vendor/Oxanium.ttf', '/vendor/MaterialIcons-Regular.ttf',
                             '/assets/service-worker.js'):
                    status, headers, _ = Request(path)
                    assert status == 200, (path, status)
                    assert 'Access-Control-Allow-Origin' not in headers
                    assert headers.get('Cross-Origin-Resource-Policy') == 'same-origin', path
                    assert 'no-store' in headers.get('Cache-Control', ''), path
                status, _, data = Request('/api/status')
                state = json.loads(data)
                assert status == 200 and state['disabled']['ethernet'] and state['disabled']['mass_storage']
                assert Request('/api/ethernet/enable', 'POST', requestOrigin=origin)[0] == 403
                assert Request('/api/storage/select', 'POST', requestOrigin=origin, body='{}')[0] == 403
                assert Request('/api/video/stop', 'POST', requestOrigin='http://foreign.invalid')[0] == 403
                assert Request('/api/video/stop', 'POST')[0] == 403
                for credentials, requestOrigin, expected in ((None, origin, 401),
                        (auth, 'http://foreign.invalid', 403), (auth, origin, 101)):
                    client, actual = Upgrade(credentials, requestOrigin)
                    try:
                        assert actual == expected, (actual, expected)
                        if actual == 101:
                            SendText(client, marker)
                            time.sleep(0.3)
                    finally:
                        client.close()
                    assert Request('/health')[0] == 200
                if platform.machine() == 'x86_64':
                    browser = shutil.which('google-chrome') or shutil.which('chromium')
                    assert browser, 'No Chromium browser available on AMD64 runner'
                    browserScript = Path(__file__).with_name('browser_privacy.mjs')
                    subprocess.run(['node', '--experimental-websocket', str(browserScript), browser, origin, user, password],
                                   check=True, timeout=50)
                badAuth = 'Basic ' + base64.b64encode(b'wrong:wrong').decode()
                for _ in range(5):
                    assert Request('/health', credentials=badAuth)[0] == 401
                assert Request('/health', credentials=badAuth)[0] == 429
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        assert marker not in logPath.read_text(errors='replace'), 'Input payload leaked to DEBUG logs'
        trace = tracePath.read_text(errors='replace')
        addresses = re.findall(r'inet_addr\("([^"]+)"\)|inet_pton\(AF_INET6, "([^"]+)"', trace)
        external = []
        for v4, v6 in addresses:
            ip = ipaddress.ip_address(v4 or v6)
            if not ip.is_loopback and not (getattr(ip, 'ipv4_mapped', None) and ip.ipv4_mapped.is_loopback):
                external.append(str(ip))
        assert not external, f'Unexpected IP destinations: {external}'
        print('No non-loopback IP destinations observed in traced KV socket calls.')
        print('Runtime authentication, rate limiting, origin, local assets, USB defaults and input-log checks passed.')


def UploadImage(filename, data):

    boundary = 'kv-' + secrets.token_hex(12)
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
    conn = http.client.HTTPConnection(host, port, timeout=10)
    try:
        conn.request('POST', '/api/storage/upload', body, {
            'Authorization': auth, 'Origin': origin,
            'Content-Type': f'multipart/form-data; boundary={boundary}'
        })
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()


def RunStorageTests(binary):

    with tempfile.TemporaryDirectory() as work:
        env = os.environ.copy()
        env.update(KV_USER=user, KV_PASSWORD=password, LOG_LEVEL='debug')
        logPath = Path(work) / 'kv-storage.log'
        diskPath = Path(work) / 'disk-images'
        outsidePath = Path(work) / 'outside.img'
        outsidePath.write_bytes(b'untouched outside image')
        with logPath.open('wb') as log:
            process = subprocess.Popen([binary, '-p', str(port), '--hotplug-interval=1',
                                        '--enable-mass-storage', '--enable-ethernet'],
                                       env=env, cwd=work, stdout=log, stderr=log, start_new_session=True)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Opt-in KV process exited during startup')
                    try:
                        if Request('/health')[0] == 200:
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError('Opt-in KV process did not start')
                status, _, data = Request('/api/status')
                state = json.loads(data)
                assert status == 200 and not state['disabled']['ethernet'] and not state['disabled']['mass_storage']
                status, _, data = Request('/api/storage/images')
                assert status == 200 and json.loads(data)['images'] == []
                assert not state['ecm']['enabled'], 'Ethernet started without explicit activation'
                payload = b'test raw virtual disk'
                status, result = UploadImage('test.img', payload)
                assert status == 200 and result['success'], result
                assert (diskPath / 'test.img').read_bytes() == payload
                status, result = UploadImage('test.img', b'overwrite attempt')
                assert not result['success'] and (diskPath / 'test.img').read_bytes() == payload
                status, result = UploadImage('compressed.gz', gzip.compress(payload))
                assert status == 200 and result['success'], result
                assert (diskPath / 'compressed.img').read_bytes() == payload
                for filename, content in [('bad name.img', payload), ('bad.gz', b'not gzip'),
                                          ('unsupported.qcow2', payload), ('empty.img', b'')]:
                    status, result = UploadImage(filename, content)
                    assert not result['success'], filename
                (diskPath / 'link.img').symlink_to(outsidePath)
                status, _, data = Request('/api/storage/images')
                assert sorted(json.loads(data)['images']) == ['compressed.img', 'test.img']
                for name in ('../outside.img', 'link.img', str(outsidePath)):
                    status, _, data = Request('/api/storage/select', 'POST', requestOrigin=origin,
                                              body=json.dumps({'image': name}))
                    assert not json.loads(data)['success'], name
                status, _, data = Request('/api/storage/images/link.img', 'DELETE', requestOrigin=origin)
                assert not json.loads(data)['success']
                assert outsidePath.read_bytes() == b'untouched outside image'
                status, _, data = Request('/api/storage/images/test.img', 'DELETE', requestOrigin=origin)
                assert status == 200 and json.loads(data)['success']
                assert not (diskPath / 'test.img').exists()
                assert sorted(path.name for path in diskPath.iterdir()) == ['compressed.img', 'link.img']
                print('Opt-in capabilities, raw/gzip uploads, invalid images, duplicate uploads, traversal and symlink checks passed.')
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


if __name__ == '__main__':
    try:
        RunTests(str(Path(sys.argv[1]).resolve()))
        RunStorageTests(str(Path(sys.argv[1]).resolve()))
    except Exception as e:
        trbk = f'Exception! {e.__class__.__name__}: {e}\n{traceback.format_exc()}'
        print(trbk)
        sys.exit(1)
