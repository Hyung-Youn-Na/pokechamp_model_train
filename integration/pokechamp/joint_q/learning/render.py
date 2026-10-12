"""A target-free renderer with an explicit token position for every legal ID."""
from dataclasses import dataclass
import hashlib
import json
from ..serializer import JointInput, render as public_render
from ..storage import digest
from .config import CONFIG, RENDERER


@dataclass(frozen=True)
class EncodedInput:
    action_ids: tuple[str,...]
    input_ids: tuple[int,...]
    readout_positions: tuple[int,...]
    prompt_sha256: str

    def __post_init__(self):
        check_length(len(self.input_ids))
        if (not self.action_ids or len(set(self.action_ids)) != len(self.action_ids)
                or len(self.action_ids) != len(self.readout_positions)
                or tuple(sorted(set(self.readout_positions))) != self.readout_positions
                or any(p < 0 or p >= len(self.input_ids) for p in self.readout_positions)):
            raise ValueError('invalid candidate/readout position binding')

    def to_row(self, observation_id):
        return dict(observation_id=observation_id, renderer=RENDERER, action_ids=self.action_ids,
                    input_ids=self.input_ids, readout_positions=self.readout_positions,
                    tokens=len(self.input_ids), prompt_sha256=self.prompt_sha256,
                    token_sha256=digest(self.input_ids))

    @classmethod
    def from_row(cls, row):
        if row['renderer'] != RENDERER or digest(row['input_ids']) != row['token_sha256']:
            raise ValueError('token cache identity mismatch')
        return cls(tuple(row['action_ids']),tuple(row['input_ids']),
                   tuple(row['readout_positions']),row['prompt_sha256'])


def check_length(length):
    if not 0 < length <= CONFIG['max_tokens']:
        raise ValueError(f'input length {length} outside 1..{CONFIG["max_tokens"]}; truncation forbidden')


def render(value, tokenizer):
    if type(value) is not JointInput:
        raise TypeError('joint value renderer accepts JointInput only')
    # Preserve the complete public state/instructions. The assistant readout
    # suffix contains only legal IDs, never target values or generated text.
    prefix, _ = public_render(value,tokenizer)
    blocks = ['ACTION_ID='+json.dumps(aid,ensure_ascii=False)+'\nQ_VALUE=' for aid in value.action_ids]
    prompt = prefix + '\n\n'.join(blocks)
    ends, cursor = [], len(prefix)
    for block in blocks:
        cursor += len(block)
        ends.append(cursor)
        cursor += 2
    encoded = tokenizer(prompt,add_special_tokens=False,return_offsets_mapping=True,
                        truncation=False,return_attention_mask=False)
    ids, offsets = encoded['input_ids'], encoded['offset_mapping']
    check_length(len(ids))
    locations = {tuple(offset):i for i,offset in enumerate(offsets)}
    positions = []
    for end in ends:
        pos = locations.get((end-1,end))
        if pos is None or prompt[end-1:end] != '=' or tokenizer.decode([ids[pos]]) != '=':
            raise ValueError('Q_VALUE= must end at its own existing = token')
        positions.append(pos)
    if tokenizer.decode(ids,skip_special_tokens=False) != prompt:
        raise ValueError('tokenizer did not preserve the complete prompt')
    return EncodedInput(value.action_ids,tuple(ids),tuple(positions),
                        hashlib.sha256(prompt.encode()).hexdigest())
