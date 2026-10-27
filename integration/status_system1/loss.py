"""Single unpadded row: dynamic candidate CE; no completion or model loading."""
import torch
import torch.nn.functional as F


def choice_loss(last_vocab_logits, label_ids, target):
    """last_vocab_logits is [V] at the last real input token, not a padding token."""
    if last_vocab_logits.ndim != 1 or len(label_ids)<2 or len(set(label_ids))!=len(label_ids) or not 0<=target<len(label_ids):
        raise ValueError('Invalid candidate readout')
    scores=last_vocab_logits[label_ids].float()
    return F.cross_entropy(scores[None],torch.tensor([target],device=scores.device))
