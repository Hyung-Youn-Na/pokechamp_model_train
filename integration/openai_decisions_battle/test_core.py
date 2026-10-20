"""신규 공급자 형식·합법 선택 경계의 무외부호출 검사."""
import copy
import json
import unittest

import httpx
from integration.pokechamp import jev_battle as j
from integration.openai_decisions.client import DecisionsError
from .core import MODEL, from_request, to_request, normalized_response, call_http

PAYLOAD=dict(state=dict(version='jev-choice-v6',text='한글',unknown=None),questions=dict(action=dict(
    type='choice',instructions='choose',criteria={'move_1':{'slot':1},'switch_2':{'slot':2}})))


class CoreTests(unittest.TestCase):
    def test_limit_counts_actual_inputs_not_protocol_frames(self):
        from .session import decision_limit_reached
        records=[dict(type='protocol') for _ in range(1000)]
        records += [dict(type='input',decision='other-1') for _ in range(700)]
        self.assertFalse(decision_limit_reached(records,'self',300))
        self.assertTrue(decision_limit_reached(records,'self',301))
        records += [dict(type='input',decision='self-'+str(i)) for i in range(600)]
        self.assertTrue(decision_limit_reached(records,'self',10))

    def test_lossless(self):
        original=copy.deepcopy(PAYLOAD)
        request=to_request(PAYLOAD)
        self.assertEqual(from_request(request),original)
        self.assertEqual(PAYLOAD,original)
        self.assertEqual([c['value'] for c in request['questions'][0]['choices']],['move_1','switch_2'])

    def test_extra_information_not_dropped(self):
        with self.assertRaises(ValueError):to_request(dict(PAYLOAD,extra='unknown schema'))

    def test_original_choice_even_when_probability_disagrees(self):
        raw=dict(model=MODEL,answers=[dict(type='choice',name='action',choice='switch_2',confidence=.1,
            probabilities=[dict(value='move_1',probability=.9),dict(value='switch_2',probability=.1)])])
        body=normalized_response(raw);criteria=PAYLOAD['questions']['action']['criteria']
        self.assertEqual(j.validate_answer(body,criteria),'switch_2')
        self.assertIn('choice_not_maximum',j.judgment_diagnostics(body['answers']['action'],criteria))
        self.assertIsInstance(raw['answers'][0]['probabilities'],list)

    def test_unusable_choice(self):
        cases=[[],[dict(type='refusal',name='action')],
               [dict(type='choice',name='action',choice='outside')],
               [dict(type='choice',name='wrong',choice='move_1')]]
        for answers in cases:
            with self.assertRaises(j.UnusableChoice):
                j.validate_answer(normalized_response(dict(model=MODEL,answers=answers)),
                                  PAYLOAD['questions']['action']['criteria'])

    def test_model_mismatch(self):
        with self.assertRaises(DecisionsError):normalized_response(dict(model='wrong',answers=[]))

    def test_auxiliary_missing_is_diagnostic(self):
        body=normalized_response(dict(model=MODEL,answers=[dict(type='choice',name='action',choice='move_1')]))
        self.assertEqual(j.validate_answer(body,PAYLOAD['questions']['action']['criteria']),'move_1')

    def test_http_failure_no_retry_and_redacted(self):
        for status in (302,400,401,403,404,429,500):
            events=[]
            with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(status,text='secret-key'))) as c:
                with self.assertRaises(DecisionsError):
                    call_http(to_request(PAYLOAD),'secret-key',events.append,decision='x',request_number=1,client=c)
            self.assertEqual(sum(e['type']=='transport' for e in events),1)
            self.assertNotIn('secret-key',json.dumps(events))

    def test_success_wire(self):
        request=to_request(PAYLOAD);events=[]
        def handler(r):
            self.assertEqual(json.loads(r.content),request)
            self.assertEqual(r.headers['authorization'],'Bearer secret-key')
            return httpx.Response(200,json=dict(model=MODEL,answers=[dict(type='choice',name='action',choice='move_1')]))
        with httpx.Client(transport=httpx.MockTransport(handler)) as c:
            result=call_http(request,'secret-key',events.append,decision='x',request_number=1,client=c)
        self.assertEqual(result['answers']['action']['choice'],'move_1')
        self.assertEqual(len(events),3)


if __name__=='__main__':unittest.main()
