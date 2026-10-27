import copy
import math
import tempfile
import unittest
from pathlib import Path
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel as DDP
from integration.jevk5_ruleqa_training.data import project,render,read_rows,read_json
from integration.jevk5_ruleqa_training.config import OUTPUT
from integration.jevk5_ruleqa_training.metrics import probabilities,score,summarize,fit_temperature,choose
from integration.jevk5_ruleqa_training.model import ChoiceReadout

class Toy(torch.nn.Module):
    def __init__(self):
        super().__init__(); self.weight=torch.nn.Parameter(torch.arange(12,dtype=torch.float64).reshape(3,4)/20)
    def forward(self,x):return x@self.weight

def ddp_worker(rank,path,result):
    dist.init_process_group('gloo',init_method='file://'+path,rank=rank,world_size=3)
    model=Toy();ddp=DDP(model)
    from contextlib import nullcontext
    for micro in range(8):
        index=micro*3+rank
        x=torch.tensor([[1.,index/24.,(index%5)/5]],dtype=torch.float64)
        with ddp.no_sync() if micro<7 else nullcontext():
            torch.nn.functional.cross_entropy(ddp(x),torch.tensor([index%4])).div(8).backward()
    torch.save(model.weight.grad, result+str(rank))
    dist.destroy_process_group()

class Tests(unittest.TestCase):
    def test_independent_ce_gradient(self):
        z=torch.tensor([math.log(2),math.log(3),math.log(5),100.],dtype=torch.float64,requires_grad=True)
        loss=torch.nn.functional.cross_entropy(z[:3][None],torch.tensor([1]));loss.backward()
        self.assertAlmostEqual(float(loss.detach()),-math.log(.3),places=12)
        torch.testing.assert_close(z.grad,torch.tensor([.2,-.7,.5,0.],dtype=torch.float64))
        self.assertEqual(probabilities([1,1,1]).argmax(),0)
        roots=[math.sqrt(x) for x in (2,3,5)]
        for temperature,expected in [(1.,[.2,.3,.5]),(2.,[x/sum(roots) for x in roots])]:
            actual=probabilities([math.log(2),math.log(3),math.log(5)],temperature)
            for got,want in zip(actual,expected):self.assertAlmostEqual(float(got),want,places=12)

    def test_actual_ddp_accumulation(self):
        with tempfile.TemporaryDirectory() as temp:
            mp.spawn(ddp_worker,args=(temp+'/init',temp+'/grad'),nprocs=3,join=True)
            model=Toy();x=torch.tensor([[1.,i/24.,(i%5)/5] for i in range(24)],dtype=torch.float64)
            torch.nn.functional.cross_entropy(model(x),torch.tensor([i%4 for i in range(24)])).backward()
            for rank in range(3):torch.testing.assert_close(torch.load(temp+'/grad'+str(rank)),model.weight.grad,rtol=1e-12,atol=1e-12)

    def test_readout_last_position_restriction(self):
        class Fake(torch.nn.Module):
            def forward(self,input_ids,logits_to_keep,use_cache):
                from types import SimpleNamespace
                self_args=(logits_to_keep,use_cache)
                assert self_args==(1,False)
                return SimpleNamespace(logits=torch.tensor([[[100.,-1.,3.,2.,200.]]]))
        got=ChoiceReadout(Fake())(torch.tensor([[9,8]]),torch.tensor([1,2,3]))
        torch.testing.assert_close(got,torch.tensor([-1.,3.,2.]))

    def test_prepared_counts_and_epoch_coverage(self):
        import random
        for split,n in [('train',1536),('validation',192),('test',192)]:
            rows=read_rows(OUTPUT/f'{split}.jsonl');self.assertEqual(len(rows),n)
            self.assertEqual({len(r['label_ids']) for r in rows},{3,4} if split=='train' else {4})
            self.assertTrue(all(sum(r['expected'])==1 and r['expected'][r['target']]==1 for r in rows))
        for epoch in range(3):
            order=list(range(1536));random.Random(20261020+epoch).shuffle(order)
            seen=[i for update in range(64) for rank in range(3) for i in order[update*24:(update+1)*24][rank::3]]
            self.assertEqual(sorted(seen),list(range(1536)))

    def test_calibration_metrics(self):
        rows=[]
        for i,target in enumerate([0,1]):
            row=dict(id=str(i),rule_id='R',group_id='g',component=0,option_ids=['A','B','C'],target=target)
            row.update(score(row,[0.,0.,0.]));rows.append(row)
        m=summarize(rows)
        self.assertAlmostEqual(m['nll'],math.log(3));self.assertAlmostEqual(m['brier'],2/3)
        self.assertAlmostEqual(m['ece'],1/6);self.assertEqual(m['accuracy'],.5)
        self.assertEqual(fit_temperature(rows)['temperature'],1.)
        self.assertEqual(choose([dict(epoch=i,metrics=m) for i in [3,2,1]])['epoch'],1)

if __name__=='__main__':unittest.main()

class LoadRecoveryTest(unittest.TestCase):
    def test_async_sync_weight_loading_identical(self):
        import os
        from unittest.mock import patch
        from transformers import LlamaConfig,LlamaForCausalLM,AutoModelForCausalLM
        with tempfile.TemporaryDirectory() as directory:
            torch.manual_seed(42)
            original=LlamaForCausalLM(LlamaConfig(vocab_size=32,hidden_size=16,intermediate_size=24,
                num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=1)).to(torch.bfloat16)
            original.save_pretrained(directory)
            with patch.dict(os.environ,HF_DEACTIVATE_ASYNC_LOAD='0'):
                async_model=AutoModelForCausalLM.from_pretrained(directory,dtype=torch.bfloat16)
            with patch.dict(os.environ,HF_DEACTIVATE_ASYNC_LOAD='1'):
                sync_model=AutoModelForCausalLM.from_pretrained(directory,dtype=torch.bfloat16)
            for name,p in original.state_dict().items():
                self.assertTrue(torch.equal(p,async_model.state_dict()[name]))
                self.assertTrue(torch.equal(p,sync_model.state_dict()[name]))
