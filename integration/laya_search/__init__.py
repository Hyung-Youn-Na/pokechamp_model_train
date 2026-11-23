"""EP-243 / D-219: Multi-turn online search (2-A), neural state value (2-B), and offline MCTS-5k Q rerank (1-B).

Strictly allocates physical GPU 0 and GPU 1 only (GPUs 2 and 3 are reserved for another project).
Preserves all existing packages (`laya_v10`..`laya_v13`, `laya_value`, `laya_foe`, `laya_fp1`, `laya_regret`,
`laya_distill`, `foulplay`, `.tools/foul-play/src`) byte-for-byte.
"""
