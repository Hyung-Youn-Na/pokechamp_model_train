"""Loss examples only: no model loading or training side effects."""
import torch
import torch.nn.functional as F


def class_loss(logits, targets, weights=None):
    """Six-class logits; optional per-example weights normalized by their sum."""
    if logits.ndim != 2 or logits.shape[1] != 6:
        raise ValueError('Expected [batch, 6] logits')
    losses = F.cross_entropy(logits.float(), targets, reduction='none')
    if weights is None:
        return losses.mean()
    weights = weights.to(losses)
    if weights.shape != losses.shape or not torch.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError('Invalid sample weights')
    return (losses * weights).sum() / weights.sum()


def choice_loss(vocab_logits, attention_mask, label_ids, targets, weights=None):
    """Read six token scores at each last real input position; supports either padding side.

    vocab_logits: [B,L,V]; attention_mask: [B,L]; label_ids: [B,6].
    No assistant answer token or completion loss is used.
    """
    if vocab_logits.shape[:2] != attention_mask.shape or not attention_mask.bool().any(dim=1).all():
        raise ValueError('Invalid attention mask')
    positions = torch.arange(attention_mask.shape[1], device=attention_mask.device)
    last = positions.expand_as(attention_mask).masked_fill(~attention_mask.bool(), -1).max(dim=1).values
    scores = vocab_logits[torch.arange(len(last), device=last.device), last]
    scores = scores.gather(1, label_ids)
    return class_loss(scores, targets, weights)
