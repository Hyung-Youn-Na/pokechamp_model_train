import unittest
import torch
from transformers import GPT2Config, GPT2LMHeadModel, AutoTokenizer
from integration.pokechamp.rule_qa_training.config import MODEL
from integration.pokechamp.rule_qa_training.data import encode
from integration.pokechamp.rule_qa_training.metrics import score, choose, bootstrap


class CoreTests(unittest.TestCase):
    def test_selected_logits_loss_and_gradient(self):
        torch.manual_seed(4)
        model=GPT2LMHeadModel(GPT2Config(vocab_size=31,bos_token_id=0,eos_token_id=0,n_embd=16,n_layer=1,n_head=2,
                             resid_pdrop=0,embd_pdrop=0,attn_pdrop=0))
        ids=torch.tensor([[1,2,3,4,5,6,7]])
        labels=ids.clone();labels[:,:4]=-100
        full=model(ids,labels=labels).loss
        full.backward();grads=[p.grad.clone() for p in model.parameters()]
        model.zero_grad()
        hidden=model.transformer(ids).last_hidden_state
        selected=model.lm_head(hidden[:,3:6])
        loss=torch.nn.functional.cross_entropy(selected.flatten(0,1),ids[:,4:].flatten())
        loss.backward()
        torch.testing.assert_close(full,loss)
        for expected,param in zip(grads,model.parameters()):torch.testing.assert_close(expected,param.grad)

    def test_qwen_native_selected_positions(self):
        from transformers import Qwen3_5TextConfig, Qwen3_5ForCausalLM
        from integration.pokechamp.rule_qa_training.model import native_gdn, assistant_loss
        native_gdn()
        config=Qwen3_5TextConfig(vocab_size=32,hidden_size=32,intermediate_size=64,
            num_hidden_layers=2,num_attention_heads=4,num_key_value_heads=2,head_dim=8,
            layer_types=['linear_attention','full_attention'],
            linear_key_head_dim=8,linear_value_head_dim=8,linear_num_key_heads=2,
            linear_num_value_heads=4,rope_parameters=dict(rope_type='default',rope_theta=10000,
                partial_rotary_factor=.5,mrope_section=[1,1,0]),eos_token_id=0,pad_token_id=0)
        model=Qwen3_5ForCausalLM(config).eval()
        row=dict(input_ids=[1,2,3,4,5,6,7,8],prefix_length=4)
        ids=torch.tensor([row['input_ids']]);labels=ids.clone();labels[:,:4]=-100
        standard=model(ids,labels=labels,use_cache=False).loss
        standard.backward(); expected={n:p.grad.clone() for n,p in model.named_parameters() if p.grad is not None}
        model.zero_grad()
        selected=assistant_loss(model,row,'cpu');selected.backward()
        torch.testing.assert_close(standard,selected)
        for n,p in model.named_parameters():
            if n in expected:torch.testing.assert_close(expected[n],p.grad,atol=1e-6,rtol=1e-4)

    def test_native_mask(self):
        tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
        messages=[dict(role='system',content='Answer briefly.'),dict(role='user',content='2+2?'),dict(role='assistant',content='4\nAddition.')]
        row=encode(tokenizer,messages)
        prefix=tokenizer.decode(row['input_ids'][:row['prefix_length']])
        target=tokenizer.decode(row['input_ids'][row['prefix_length']:])
        self.assertIn('<think>\n\n</think>',prefix)
        self.assertEqual(target,'4\nAddition.<|im_end|>')

    def test_strict_mc(self):
        row=dict(representation='state_mc',options=[dict(id=c) for c in 'ABC'],answer_id='B')
        for text in ['B','B. Answer\nReason','B: answer','B) answer']:
            self.assertTrue(score(row,text)['correct'],text)
        for text in ['Answer: B','B or C','B. or C.','D. answer','reason\nB. answer','']:
            self.assertFalse(score(row,text)['correct'],text)

    def test_selection_ties_and_bootstrap(self):
        def item(epoch,acc,nll):return dict(epoch=epoch,metrics=dict(forms=dict(state_mc=dict(accuracy=acc)),assistant_nll=nll))
        self.assertEqual(choose([item(3,.5,1),item(2,.5,1),item(1,.4,.1)])['epoch'],2)
        base=[dict(id=str(i),representation='state_mc',component=i//2,correct=False) for i in range(8)]
        tuned=[dict(r,correct=True) for r in base]
        result=bootstrap(base,tuned,repetitions=100)
        self.assertEqual(result['components'],4)
        self.assertEqual(result['ci95'],[1.,1.])


if __name__=='__main__':unittest.main()
