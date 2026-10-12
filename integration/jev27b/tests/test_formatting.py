"""Behavioral tests for the lossless native Choice boundary; no model imports/downloads."""
import copy
import json
import math
import unittest

from integration.jev27b.formatting import (
    InputTooLong, InputValidationError, answer_from_probabilities, format_request, tokenize_request,
)


def request():
    return {"state": {"turn": 9, "log": "A\nB", "details": {"speed": None, "name": "포켓몬"}},
            "questions": {"action": {"type": "choice", "instructions": "Keep all facts.\nChoose the best action.",
                                      "criteria": {
                                          "move-4-tera": {"kind": "move", "slot": 4, "tera": True,
                                                          "damage": {"opponent": [0.2, 0.4]}},
                                          "switch-2": {"kind": "switch", "slot": 2, "hint": "first\nsecond"},
                                      }}}}


class FakeTokenizer:
    def __init__(self, length):
        self.length = length
        self.calls = []

    def __call__(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return {"input_ids": list(range(self.length)), "attention_mask": [1] * self.length}


class FormattingTests(unittest.TestCase):
    def test_full_state_instructions_and_ordered_candidate_objects_survive(self):
        payload = request()
        original = copy.deepcopy(payload)
        formatted = format_request(payload)
        prefix = "[kind] choice\n[state] "
        state, rest = formatted.prompt[len(prefix):].split("\n[question] ", 1)
        instructions, options = rest.split("\n[options]\n", 1)
        self.assertEqual(json.loads(state), payload["state"])
        self.assertEqual(instructions, payload["questions"]["action"]["instructions"])
        option_lines = options.removesuffix("\n[decision]:").splitlines()
        self.assertEqual(len(option_lines), 2)
        self.assertEqual([line[:3] for line in option_lines], ["A) ", "B) "])
        restored = {}
        for line in option_lines:
            restored.update(json.loads(line[3:]))
        self.assertEqual(list(restored), ["move-4-tera", "switch-2"])
        self.assertEqual(restored, payload["questions"]["action"]["criteria"])
        self.assertEqual(payload, original)

    def test_slot_probabilities_map_to_original_ids_with_first_tie(self):
        formatted = format_request(request())
        answer = answer_from_probabilities(formatted, [0.1, 0.9])
        self.assertEqual(answer["choice"], "switch-2")
        self.assertEqual(answer["probabilities"], {"move-4-tera": 0.1, "switch-2": 0.9})
        self.assertEqual(answer["confidence"], 0.9)
        self.assertEqual(answer_from_probabilities(formatted, [0.5, 0.5])["choice"], "move-4-tera")
        reverse = request()
        reverse["questions"]["action"]["criteria"] = dict(reversed(list(reverse["questions"]["action"]["criteria"].items())))
        self.assertEqual(answer_from_probabilities(format_request(reverse), [0.5, 0.5])["choice"], "switch-2")

    def test_whole_prompt_tokenization_without_specials_padding_or_truncation(self):
        formatted = format_request(request())
        tokenizer = FakeTokenizer(32768)
        encoded = tokenize_request(tokenizer, formatted)
        self.assertEqual(len(encoded["input_ids"]), 32768)
        self.assertEqual(tokenizer.calls, [(formatted.prompt, {"add_special_tokens": False,
                         "truncation": False, "padding": False, "return_attention_mask": True})])
        tokenizer = FakeTokenizer(32769)
        with self.assertRaises(InputTooLong) as caught:
            tokenize_request(tokenizer, formatted)
        self.assertEqual(caught.exception.token_count, 32769)
        self.assertEqual(caught.exception.max_tokens, 32768)
        self.assertEqual(tokenizer.calls[0][0], formatted.prompt)

    def test_single_candidate_requires_the_existing_no_call_path(self):
        payload = request()
        payload["questions"]["action"]["criteria"].pop("switch-2")
        with self.assertRaisesRegex(InputValidationError, "bypass inference"):
            format_request(payload)

    def test_sixteen_slots_work_and_seventeen_are_rejected(self):
        payload = request()
        payload["questions"]["action"]["criteria"] = {f"id-{i}": {"slot": i} for i in range(16)}
        formatted = format_request(payload)
        self.assertIn('P) {"id-15": {"slot": 15}}\n[decision]:', formatted.prompt)
        payload["questions"]["action"]["criteria"]["id-16"] = {"slot": 16}
        with self.assertRaises(InputValidationError):
            format_request(payload)

    def test_nonfinite_json_and_bad_model_probabilities_are_rejected(self):
        payload = request()
        payload["state"]["invalid"] = math.nan
        with self.assertRaises(InputValidationError):
            format_request(payload)
        formatted = format_request(request())
        for probabilities in ([0.5], [math.nan, 0.2], [math.inf, 0.2], [-0.1, 1.1], [0.2, 0.2], [True, False]):
            with self.subTest(probabilities=probabilities), self.assertRaises(InputValidationError):
                answer_from_probabilities(formatted, probabilities)

    def test_structured_instructions_and_string_state_are_lossless(self):
        payload = request()
        payload["state"] = "Exact state.\nSecond line."
        instructions = ["First instruction", {"second": [1, None, "가"]}]
        payload["questions"]["action"]["instructions"] = instructions
        formatted = format_request(payload)
        self.assertIn("[state] Exact state.\nSecond line.\n[question] ", formatted.prompt)
        section = formatted.prompt.split("\n[question] ", 1)[1].split("\n[options]", 1)[0]
        self.assertEqual(json.loads(section), instructions)

    def test_malformed_question_is_not_silently_repaired(self):
        for mutate in (
            lambda p: p.pop("state"),
            lambda p: p["questions"]["action"].update(type="score"),
            lambda p: p["questions"].update(extra=copy.deepcopy(p["questions"]["action"])),
            lambda p: p["questions"]["action"]["criteria"].update(illegal="not an object"),
        ):
            payload = request()
            mutate(payload)
            with self.assertRaises(InputValidationError):
                format_request(payload)


if __name__ == "__main__":
    unittest.main()
