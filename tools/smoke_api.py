"""Exercise production startup without an Arduino inside an isolated container."""
import http.client
import json
import os
import signal
import subprocess
import sys
import time


def request(method, path, payload=None):
    connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=2)
    try:
        headers = {'Content-Type': 'application/json'}
        connection.request(method, path, json.dumps(payload) if payload is not None else None, headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


environment = dict(os.environ, ARDUINO_PORT='/dev/nonexistent', STATUS_PORT='8080',
                   AUDIO_ENABLED='0')
process = subprocess.Popen([sys.executable, '-m', 'app.app'], env=environment)
try:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            status, health = request('GET', '/health')
            if health['phase'] == 'FAULT':
                break
        except OSError:
            pass
        time.sleep(0.05)
    assert status == 503 and 'NO SERIAL DEVICE FOUND' in health['fault']['message'], health
    assert request('GET', '/diagnostics')[0] == 200
    status, operation = request('POST', '/maintenance', {})
    assert status == 202
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        _, result = request('GET', '/operations/' + operation['id'])
        if result['status'] == 'DONE':
            break
        time.sleep(0.05)
    assert result['status'] == 'DONE', result
    assert request('GET', '/configuration')[0] == 200
    assert request('POST', '/serial', {'command': 'RFID STATUS'})[0] == 503
    assert request('GET', '/host')[0] == 503  # host bridge intentionally absent in this test
    print('PRODUCTION API SMOKE TEST PASSED')
finally:
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
