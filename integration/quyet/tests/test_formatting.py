import pytest
from integration.quyet.formatting import prepare, InputTooLong
from integration.quyet.tests.test_policy import payload
from integration.quyet.policy import type_request, detail_request


class Tokenizer:
    def __init__(self,state_count=50,prompt_count=100):
        self.state_count,self.prompt_count=state_count,prompt_count
    def __call__(self,text,**kwargs):
        assert kwargs.get('truncation',False) is False
        return {'input_ids':[1]*(self.prompt_count if text.startswith('CHAT:') else self.state_count)}
    def apply_chat_template(self,msgs,**kwargs):
        assert kwargs['enable_thinking'] is False
        return 'CHAT:' + '\n'.join(m['content'] for m in msgs)


def test_official_v1_full_candidate_description_order():
    p=type_request(payload());f=prepare(Tokenizer(),p,strict=True)
    assert f.candidate_ids==('move','switch') and f.state_tokens==50
    assert 'You are a decision model.' in f.prompt and 'Answer with one letter.' in f.prompt
    assert all(k in f.prompt for k in payload()['questions']['action']['criteria'])
    assert f.evidence()['strict'] is True and f.evidence()['truncated'] is False


@pytest.mark.parametrize('state,prompt',[(32769,100),(50,32769)])
def test_no_truncation_over_either_limit(state,prompt):
    with pytest.raises(InputTooLong): prepare(Tokenizer(state,prompt),type_request(payload()),strict=True)


def test_exact_limit_and_strict_required():
    assert len(prepare(Tokenizer(32768,32768),type_request(payload()),strict=True).token_ids)==32768
    with pytest.raises(ValueError,match='strict'): prepare(Tokenizer(),type_request(payload()),strict=False)


def test_official_ten_candidate_cap_unchanged():
    with pytest.raises(ValueError): prepare(Tokenizer(),payload(),strict=True)
    assert len(prepare(Tokenizer(),detail_request(payload(),'move'),strict=True).candidate_ids)==8
