"""Approved EX-091 package identity; the existing JEV environment is reused."""
from integration.jev27b.config import ROOT, MAX_TOKENS

MODEL_ID = 'ytbai/MiniCPM5-2B-Jev'
REVISION = '27afc6f17ceb7eb95b6442047ec54e43fbed5ed1'
BASE_MODEL_ID = 'openbmb/MiniCPM5-2B'
BASE_REVISION = 'f97400052a43d642bbc6e9975e2397e3ae6a6b52'
RUNTIME = ROOT / '.pokechamp-data/minicpm5-jev-runtime'
MODEL_DIR = RUNTIME / 'model'
EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep144/model'
MAX_OPTIONS = 16
HEAD_SHAPE = (255, 2048)
NUM_LAYERS = 42
CHOICE_TEMPERATURE = 1.1314
