"""Last-real-token readout; the vocabulary outside each candidate set has zero gradient."""
import torch
import torch.nn.functional as F
from integration.jevk5_ruleqa_training.model import load_model, frozen_fingerprint


def collate(rows,pad_id,device):
    lengths=torch.tensor([len(r['input_ids']) for r in rows],device=device)
    width=int(lengths.max());k=max(len(r['label_ids']) for r in rows)
    ids=torch.full((len(rows),width),pad_id,dtype=torch.long,device=device)
    labels=torch.full((len(rows),k),-1,dtype=torch.long,device=device)
    for i,r in enumerate(rows):
        ids[i,:len(r['input_ids'])]=torch.as_tensor(r['input_ids'].copy() if hasattr(r['input_ids'],'copy') else r['input_ids'],device=device)
        labels[i,:len(r['label_ids'])]=torch.as_tensor(list(r['label_ids']),device=device)
    return dict(input_ids=ids,attention_mask=torch.arange(width,device=device)[None,:]<lengths[:,None],
                label_ids=labels,targets=torch.tensor([r['target'] for r in rows],device=device),
                weights=torch.tensor([r.get('weight',1.) for r in rows],dtype=torch.float64,device=device))


def restrict(logits,labels):
    if torch.any((labels>=0).sum(-1)<2):raise ValueError('need at least two candidates')
    return logits.gather(1,labels.clamp_min(0)).float().masked_fill(labels<0,-torch.inf)


class ChoiceReadout(torch.nn.Module):
    def __init__(self,model):super().__init__();self.model=model
    def forward(self,input_ids,attention_mask,label_ids):
        last=attention_mask.long().sum(-1)-1
        if torch.any(last<0):raise ValueError('empty input')
        positions,inverse=torch.unique(last,sorted=True,return_inverse=True)
        z=self.model(input_ids=input_ids,attention_mask=attention_mask.long(),
                     logits_to_keep=positions,use_cache=False).logits
        final=z[torch.arange(len(last),device=z.device),inverse]
        return restrict(final,label_ids)


def weighted_numerator(logits,targets,weights):
    loss=F.cross_entropy(logits,targets,reduction='none')
    if not torch.isfinite(loss).all() or not torch.isfinite(weights).all() or not (weights>0).all():
        raise FloatingPointError('invalid weighted choice loss')
    return (loss.double()*weights).sum()


def forward(reader,batch):
    with torch.autocast('cuda',dtype=torch.bfloat16,enabled=batch['input_ids'].is_cuda):
        return reader(batch['input_ids'],batch['attention_mask'],batch['label_ids'])
