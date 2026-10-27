import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from integration.jevk5_system1_training.data import TokenWriter,TokenStore,epoch_batches,microbatches,weights
from integration.jevk5_system1_training.model import ChoiceReadout,collate,restrict,weighted_numerator

class Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__();self.embedding=torch.nn.Embedding(20,6);self.head=torch.nn.Linear(6,16)
    def forward(self,input_ids,attention_mask,logits_to_keep,use_cache=False):
        # Causal context exposes accidental reads at padded positions.
        z=self.head((self.embedding(input_ids)*attention_mask[:,:,None]).cumsum(1))
        from types import SimpleNamespace
        return SimpleNamespace(logits=z[:,logits_to_keep])

class Core(unittest.TestCase):
    def test_last_real_and_candidate_gradient(self):
        torch.manual_seed(9);model=ChoiceReadout(Tiny())
        rows=[dict(input_ids=[1,3,4],label_ids=[2,4],target=1),dict(input_ids=[2],label_ids=list(range(11)),target=10)]
        batch=collate(rows,19,'cpu');z=model(batch['input_ids'],batch['attention_mask'],batch['label_ids'])
        for i,r in enumerate(rows):
            b=collate([r],19,'cpu');single=model(b['input_ids'],b['attention_mask'],b['label_ids'])
            torch.testing.assert_close(z[i,:len(r['label_ids'])],single[0])
        vocab=torch.randn(2,16,requires_grad=True);labels=batch['label_ids'];c=restrict(vocab,labels)
        weighted_numerator(c,batch['targets'],batch['weights']).backward()
        self.assertTrue((vocab.grad[0,[i for i in range(16) if i not in [2,4]]]==0).all())
        self.assertTrue((vocab.grad[1,11:]==0).all())
        remap=restrict(vocab,torch.tensor([[4,2]]).expand(2,-1))
        torch.testing.assert_close(torch.softmax(remap[0],-1).flip(0),torch.softmax(c[0,:2],-1))
    def test_weighted_accumulation_uneven_ranks(self):
        torch.manual_seed(8)
        x=torch.randn(69,5,dtype=torch.float64);w=torch.linspace(.01,5,69,dtype=torch.float64);y=torch.arange(69)%3
        p=torch.randn(5,3,dtype=torch.float64,requires_grad=True)
        loss=(torch.nn.functional.cross_entropy(x@p,y,reduction='none')*w).sum()/w.sum()
        reference=torch.autograd.grad(loss,p)[0]
        rank_grads=[]
        for rank in range(3):
            q=p.detach().clone().requires_grad_();indices=list(range(rank,69,3))
            for start in range(0,len(indices),[1,4,8][rank]):
                ix=indices[start:start+[1,4,8][rank]]
                (3*(torch.nn.functional.cross_entropy(x[ix]@q,y[ix],reduction='none')*w[ix]).sum()/w.sum()).backward()
            rank_grads.append(q.grad)
        torch.testing.assert_close(sum(rank_grads)/3,reference)
    def test_exact_epoch_and_micro_limits(self):
        for e in range(3):
            b=list(epoch_batches(130149,e));self.assertEqual(len(b),1356);self.assertEqual(len(b[-1]),69)
            self.assertEqual(sorted(i for v in b for i in v),list(range(130149)))
        lengths=[6127,1,2049,600,512,512,512,512,512,512,512,512,512]
        for limit in [8,4,2,1]:
            batches=list(microbatches(range(len(lengths)),lengths,limit))
            self.assertEqual(sorted(sum(batches,[])),list(range(len(lengths))))
            for b in batches:
                self.assertLessEqual(len(b),limit)
                self.assertTrue(len(b)==1 or max(lengths[i] for i in b)*len(b)<=4096)
    def test_memmap_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            w=TokenWriter(Path(d)/'data');w.add([1,2],[4,3],1,dict(id='a'));w.add([5],[2,1,7],0,dict(id='b'));w.close()
            s=TokenStore(Path(d)/'data');self.assertIsInstance(s.tokens,np.memmap)
            self.assertEqual(s[0]['input_ids'].tolist(),[1,2]);self.assertEqual(s[1]['label_ids'].tolist(),[2,1,7])
    def test_domain_mass(self):
        from integration.jevk5_system1_training.config import SHARES
        m=[]
        for d in SHARES:m.extend([dict(domain=d,group='a')]*4+[dict(domain=d,group='b')])
        w=weights(m)
        for d,v in SHARES.items():self.assertAlmostEqual(sum(t for r,t in zip(m,w) if r['domain']==d)/len(m),v)
        self.assertAlmostEqual(w[0]*2,w[4])

if __name__=='__main__':unittest.main()
