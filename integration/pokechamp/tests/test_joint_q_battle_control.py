"""CPU tests for EX081's input boundary, identity comparison and clock."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from integration.pokechamp.joint_q.serializer import JointInput, VERSION
from integration.pokechamp.joint_q.battle_eval import config, protocol, storage
from integration.pokechamp.joint_q.battle_eval.diagnose import compare
from integration.pokechamp.joint_q.battle_eval import diagnose, server
from integration.pokechamp.joint_q.battle_eval import control


def joint():
    return JointInput(json.dumps(dict(version=VERSION, instructions='fixed', state={},
        actions=[{'action_id': 'move_1'}, {'action_id': 'switch_2'}])))


class ContractTests(unittest.TestCase):
    def test_exact_public_only_request(self):
        value = joint()
        self.assertEqual(protocol.validate_request(protocol.request_payload(value)), value)
        body = protocol.request_payload(value)
        body['target_q'] = [.8, .2]
        with self.assertRaises(ValueError):
            protocol.validate_request(body)
        raw = json.loads(value.payload_json)
        raw['state']['private'] = 1
        with self.assertRaises(ValueError):
            protocol.validate_request({'profile': config.PROFILE, 'payload_json': json.dumps(raw)})
        duplicated = value.payload_json.replace('"state": {}', '"state": {"private":1}, "state": {}')
        with self.assertRaises(ValueError):
            protocol.validate_request({'profile': config.PROFILE, 'payload_json': duplicated})

    def test_nonfinite_input_rejected(self):
        raw = json.loads(joint().payload_json)
        raw['state']['hp'] = float('nan')
        with self.assertRaises(ValueError):
            protocol.validate_request({'profile': config.PROFILE, 'payload_json': json.dumps(raw)})

    def test_tie_order_and_single_candidate(self):
        response = dict(profile=config.PROFILE, q_values={'move_1': .2, 'switch_2': .2}, choice='move_1')
        self.assertEqual(protocol.validate_response(response, ('move_1', 'switch_2')), 'move_1')
        response['choice'] = 'switch_2'
        with self.assertRaises(ValueError):
            protocol.validate_response(response, ('move_1', 'switch_2'))
        self.assertEqual(protocol.validate_response(dict(profile=config.PROFILE,
            q_values={'move_1': 0}, choice='move_1'), ['move_1']), 'move_1')

    def test_wrong_ids_and_values(self):
        for values in ({'switch_2': 1, 'move_1': .1}, {'move_1': .1},
                       {'move_1': float('nan'), 'switch_2': .2},
                       {'move_1': True, 'switch_2': .2}, {'move_1': 10**1000, 'switch_2': .2}):
            with self.subTest(values=repr(values)[:60]), self.assertRaises(ValueError):
                protocol.validate_response(dict(profile=config.PROFILE, q_values=values, choice='move_1'),
                                           ['move_1', 'switch_2'])

    def test_exact_reference_comparison(self):
        value = joint()
        expected = dict(observation_id='v1', action_ids=['move_1', 'switch_2'],
            predicted_q=[.5, .25], prompt_sha256='abc', token_sha256='def', readout_positions=[2, 5], tokens=6)
        response = dict(profile=config.PROFILE, q_values={'move_1': .501, 'switch_2': .25},
            choice='move_1', input_sha256=protocol.input_sha256(value), prompt_sha256='abc', token_sha256='def',
            readout_positions=[2, 5], tokens=6)
        self.assertGreater(compare(response, expected, value)['maximum_q_difference'], config.TOLERANCE)
        response['tokens'] = 7
        with self.assertRaises(ValueError):
            compare(response, expected, value)

    def test_first_clock_immutable_and_cumulative(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(storage.time, 'time', return_value=100):
                first = storage.clock(temp, start=True)
            with patch.object(storage.time, 'time', return_value=110):
                self.assertEqual(storage.clock(temp, start=True), first)
                self.assertEqual(storage.remaining(temp), config.LIMITS['total_seconds'] - 10)
            with self.assertRaises(FileExistsError):
                storage.atomic(Path(temp) / 'clock.json', {}, immutable=True)

    def test_health_during_serialized_inference(self):
        active, release = threading.Event(), threading.Event()
        class Fake:
            lock = threading.Lock()
            failed = None
            def health(self):
                return {'ready': True}
            def evaluate(self, body, *, deadline):
                active.set()
                self.asserted_deadline = deadline
                if not release.wait(5):
                    raise TimeoutError('test synchronization timeout')
                return {'answer': body}
        runtime = Fake()
        http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.handler(runtime, time.time()+60))
        endpoint = f'http://127.0.0.1:{http.server_port}'
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        values = []
        client = threading.Thread(target=lambda: values.append(diagnose.request(endpoint, '/evaluate', {'x':1})))
        client.start()
        try:
            self.assertTrue(active.wait(2))
            self.assertEqual(diagnose.request(endpoint, '/health', timeout=1), {'ready': True})
        finally:
            release.set()
            client.join(5)
            http.shutdown()
            http.server_close()
            thread.join(5)
        self.assertEqual(values, [{'answer': {'x': 1}}])

    def test_closure_requires_all_integrity_flags(self):
        good = dict(returncode=0, closure=dict(weights_unchanged=True, base_unchanged=True,
            checkpoint_files_unchanged=True, source_unchanged=True, optimizer_updates=0))
        self.assertTrue(control.verified_closure(good))
        for key in ('weights_unchanged','base_unchanged','checkpoint_files_unchanged','source_unchanged'):
            bad = dict(good, closure=dict(good['closure'], **{key: False}))
            self.assertFalse(control.verified_closure(bad))
        self.assertFalse(control.verified_closure(dict(returncode=0, closure=None)))
        self.assertFalse(control.verified_closure(dict(good, returncode=1)))

    def test_status_before_clock_and_failure_timestamp(self):
        with tempfile.TemporaryDirectory() as temp:
            control.status(temp, 'waiting', at='failure-original-time', error='busy')
            result = storage.read(Path(temp) / 'status.json')
            self.assertIsNone(result['remaining_seconds'])
            self.assertEqual(result['at'], 'failure-original-time')

    def test_gpu_busy_wait_preserves_first_clock(self):
        from integration.pokechamp.joint_q.battle_eval import model_io
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'run'
            directory.mkdir()
            first = storage.clock(directory, start=True)
            busy = dict(physical_gpu=0,total_mib=49140,used_mib=2048,gpu_uuid='g',name='A6000')
            free = dict(busy,used_mib=0)
            with patch.object(config, 'ROOT', Path(temp)), patch.dict('os.environ', CUDA_VISIBLE_DEVICES='0'), \
                    patch.object(model_io, 'gpu_facts', side_effect=[busy,free]), \
                    patch.object(model_io.time, 'sleep') as pause:
                with model_io.gpu_owner(directory) as facts:
                    self.assertEqual(facts, free)
                pause.assert_called_once_with(5)
            self.assertEqual(storage.clock(directory), first)


class QualificationTests(unittest.TestCase):
    def setup_case(self, directory, deltas):
        value = joint()
        expected = dict(observation_id='v1',action_ids=list(value.action_ids),predicted_q=[.5,.25],
                        prompt_sha256='p',token_sha256='t',readout_positions=[2,5],tokens=6)
        inputs = [(dict(expected,observation_id=f'v{i}'),value) for i in range(320)]
        health = dict(profile=config.PROFILE,model=config.MODEL,revision=config.REVISION,
            checkpoint_sha256='cp',head_sha256='head',server_pid=1,server_started_at=1.0,
            source_sha256='src',physical_gpu=0,gpu_uuid='gpu',ready=True,endpoint='http://127.0.0.1:1')
        state = {'index': -1}
        def start(root, label):
            state['index'] += 1
            output = Path(root)/'server'/label
            output.mkdir(parents=True)
            return SimpleNamespace(pid=state['index']+1),output,dict(health,server_pid=state['index']+1)
        def response(*_):
            return dict(health,server_pid=state['index']+1,input_sha256=protocol.input_sha256(value),
                prompt_sha256='p',token_sha256='t',readout_positions=[2,5],tokens=6,
                q_values={'move_1': .5+deltas[state['index']], 'switch_2':.25},choice='move_1')
        closed = dict(returncode=0,closure=dict(weights_unchanged=True,base_unchanged=True,
            checkpoint_files_unchanged=True,source_unchanged=True,optimizer_updates=0))
        storage.atomic(Path(directory)/'configuration.json', {'frozen':True, 'serving_source_sha256':'src'})
        return inputs,start,response,closed

    def exercise(self, directory, deltas):
        inputs,start,response,closed = self.setup_case(directory,deltas)
        from integration.pokechamp.joint_q.battle_eval import client
        with patch.object(control,'verify_configuration'), patch.object(control,'validation_inputs',return_value=inputs), \
                patch.object(control,'start_server',side_effect=start), patch.object(control,'request',side_effect=response), \
                patch.object(control,'stop_server',return_value=closed) as stop, patch.object(client,'health'):
            try:
                result = control.qualify(directory)
            except ValueError:
                return None,stop.call_count
            return result,stop.call_count

    def test_mutual_gate_rejects_individually_allowed_opposite_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            result, stops = self.exercise(temp,[.00009,-.00009])
            self.assertIsNone(result)
            self.assertEqual(stops,2)
            self.assertFalse((Path(temp)/'qualification/passed.json').exists())
            self.assertEqual(len(list((Path(temp)/'qualification').glob('*/failure.json'))),1)

    def test_pass_retains_exact_second_process(self):
        with tempfile.TemporaryDirectory() as temp:
            result, stops = self.exercise(temp,[0,.00004])
            self.assertEqual(stops,1)
            process,_,receipt = result
            self.assertEqual(process.pid,2)
            self.assertEqual(receipt['server']['server_pid'],2)
            self.assertTrue(receipt['passed'])


if __name__ == '__main__':
    unittest.main()
