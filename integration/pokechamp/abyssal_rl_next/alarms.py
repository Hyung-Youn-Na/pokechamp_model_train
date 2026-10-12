"""EX-075의 모델 비호출 단계 감지·영속 중복 방지 대화 알람."""
from __future__ import annotations

import fcntl
import os
import subprocess
import time
from pathlib import Path

from .storage import atomic, read, sha
from . import config as runtime_config


def process_alive(pid, start_ticks):
    try:
        fields = (Path('/proc') / str(pid) / 'stat').read_text().split(') ', 1)[1].split()
        return fields[0] != 'Z' and fields[19] == str(start_ticks)
    except (FileNotFoundError, ProcessLookupError):
        return False


def events(directory, *, now=None, alive=True):
    """완료·기한만 terminal로 합치고 복구 가능한 비정상 종료는 분리한다."""
    directory = Path(directory)
    now = time.time() if now is None else now
    state_path = directory / 'state.json'
    state = read(state_path) if state_path.exists() else {}
    phase = state.get('phase')
    result = []
    selection_phases = {'calibration_collect', 'calibration_features', 'calibration_train',
                        'calibration_dev', 'lock', 'test_initial', 'test_selected', 'finalize'}
    if phase in selection_phases and (directory / 'selection.json').exists():
        result.append(('selection', 'selection.json', '학습 종료 및 마지막 dev·정책 선택 완료'))
    if phase in {'test_initial', 'test_selected', 'finalize'} and (directory / 'evaluation-lock.json').exists():
        if not (directory / 'calibration-decision.json').exists():
            raise ValueError('test lock exists without calibration decision receipt')
        result.append(('test_entry', 'evaluation-lock.json', '보정 판단 완료 및 잠긴 test 진입'))
    if (directory / 'completed.json').exists():
        result.append(('terminal', 'completed.json', '전체 최종화 종료'))
    else:
        clock = directory / 'clock.json'
        expired = clock.exists() and now >= read(clock)['deadline_at']
        if expired:
            result.append(('terminal', 'clock.json', '절대 마감 도달'))
        elif not alive:
            receipt = next((name for name in ('supervisor-exit.json', 'failure.json', 'state.json')
                            if (directory / name).exists()),
                           'manifest.json' if (directory / 'manifest.json').exists() else 'prepared/manifest.json')
            result.append(('abnormal', receipt, '실행 프로세스 종료: 최종화 receipt 미완료'))
    return result


def _message(directory, event, receipt, description):
    ending = ('종료 receipt를 한 번 확인하고 문서 갱신·최종 성능·미충족 기준·자원·보고서·뷰어 링크를 보고하세요.'
              if event == 'terminal' else '해당 단계 receipt를 한 번 확인하고 간단히 보고한 뒤 종료하세요.')
    return (f'[EX-075 단계 알람] {description}. 실행 경로: {directory}; receipt: {receipt}. '
            f'{ending} 실시간 대화형 반복 조회·대기 루프를 재개하지 마세요. '
            '자동 실행은 알람 응답을 기다리지 않습니다. 추가 예산·새 실험은 승인되지 않았습니다.')


def deliver_once(directory, config, *, now=None, sender=None):
    """queue는 idempotency API가 없어 전송 전에 claim을 영속화한다.

    전송 중 crash/timeout은 uncertain으로 보존하고 재전송하지 않는다. 모델 호출은
    수신자가 단계 알람에 응답할 때만 발생하며 이 감지기는 상태/프로세스만 읽는다.
    """
    directory = Path(directory).resolve()
    identity = directory / 'manifest.json'
    if not identity.exists():
        identity = directory / 'prepared/manifest.json'
    identity_record = read(identity)
    identity_key = 'experiment_id' if identity.name == 'manifest.json' and identity.parent == directory else 'experiment'
    if identity_record.get(identity_key) != 'EX-075':
        raise ValueError('alarm detector is restricted to EX-075')
    if not config.get('thread_verified') or not config.get('thread') or not config.get('codex'):
        raise ValueError('verified current conversation and queue executable are required')
    root = directory / 'alarms'
    root.mkdir(exist_ok=True)
    with (root / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger = root / 'delivery.json'
        record = read(ledger) if ledger.exists() else {'experiment_id': 'EX-075', 'events': {}}
        current = events(directory, now=now,
                         alive=process_alive(config['pid'], config['start_ticks']))
        for event, relative, description in current:
            if event in record['events']:
                continue
            receipt = directory / relative
            claim = dict(status='claimed', claimed_at=time.time(), receipt=relative,
                         receipt_sha256=sha(receipt), description=description)
            record['events'][event] = claim
            atomic(ledger, record)
            command = [config['codex'], 'queue', '--thread', config['thread'], '--message',
                       _message(directory, event, receipt, description)]
            try:
                response = (sender or subprocess.run)(command, cwd=runtime_config.ROOT,
                    capture_output=True, text=True, timeout=45)
                claim.update(status='delivered' if response.returncode == 0 else 'delivery_failed',
                             returncode=response.returncode, finished_at=time.time())
            except Exception as error:
                claim.update(status='uncertain', error_type=type(error).__name__, finished_at=time.time())
            # Do not persist subprocess output: it may contain session configuration.
            atomic(ledger, record)
        return record


def watch(directory, config_path, *, interval=30):
    """별도 프로세스 전용. 대화형 에이전트 polling용이 아니다."""
    if not 1 <= interval <= 60:
        raise ValueError('detector interval must be between 1 and 60 seconds')
    config = read(config_path)
    while True:
        ledger = deliver_once(directory, config)
        current = events(directory, alive=process_alive(config['pid'], config['start_ticks']))
        if any(event in {'abnormal', 'terminal'} and event in ledger['events']
               for event, _, _ in current):
            return ledger
        time.sleep(interval)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--interval', default=30, type=int)
    args = parser.parse_args()
    watch(args.directory, args.config, interval=args.interval)
