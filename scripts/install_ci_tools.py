#!/usr/bin/env python3
"""Bound package setup and expose progress through the supported Checks API."""
import json
import os
from pathlib import Path
import subprocess
import time

log = Path('/tmp/firmware-toolchain-setup.log')
payload = Path('/tmp/firmware-toolchain-check.json')
repo = os.environ['GITHUB_REPOSITORY']
run = os.environ['GITHUB_RUN_ID']
check = None


def report(phase, elapsed):
    global check
    try:
        if check is None:
            jobs = json.loads(subprocess.check_output(
                ['gh', 'api', f'repos/{repo}/actions/runs/{run}/jobs'], timeout=15))['jobs']
            check = next(j['id'] for j in jobs if j['name'] == 'build' and j['status'] == 'in_progress')
        text = log.read_text(errors='replace')[-12000:] if log.exists() else ''
        payload.write_text(json.dumps({'output': {
            'title': 'Firmware toolchain setup',
            'summary': f'{phase}: {elapsed:.0f} seconds',
            'text': '```text\n' + text + '\n```',
        }}))
        subprocess.run(['gh', 'api', '--method', 'PATCH', f'repos/{repo}/check-runs/{check}',
                        '--input', str(payload)], check=True, stdout=subprocess.DEVNULL, timeout=15)
    except (OSError, subprocess.SubprocessError, StopIteration):
        print('Progress upload unavailable; continuing package setup.', flush=True)


for phase, args in [
    ('apt update', ['update']),
    ('apt install', ['install', '-y', '--no-install-recommends', 'libclang-18-dev',
                     'libclang-common-18-dev', 'gcc-arm-none-eabi', 'libnewlib-dev']),
]:
    started = time.monotonic()
    with log.open('a') as output:
        output.write('\n' + phase + '\n')
        output.flush()
        proc = subprocess.Popen(['sudo', 'timeout', '--kill-after=10s', '300', 'apt-get', *args],
                                stdout=output, stderr=subprocess.STDOUT)
        while proc.poll() is None:
            report(phase, time.monotonic() - started)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                pass
    report(phase + (' completed' if proc.returncode == 0 else ' failed'), time.monotonic() - started)
    if proc.returncode:
        raise SystemExit(proc.returncode)
