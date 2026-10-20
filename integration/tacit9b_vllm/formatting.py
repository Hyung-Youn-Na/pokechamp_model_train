"""EX-104 official prompt contract, unchanged for externally served EX-105."""
from integration.tacit9b.formatting import (
    FormattedRequest, InputTooLong, InputValidationError, MAX_OPTIONS, MAX_TOKENS,
    ONE_FORWARD_SYSTEM, COT_SYSTEM, choice_request, format_request, render,
    tokenize_request, payload_seed, mapped_answer,
)

FORMAT_VERSION = 'tacit9b-vllm-official-always-thinking-v1'
