"""공식 Decisions HTTP API와 로컬 자격증명 설정."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from collections.abc import Mapping

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
ENDPOINT = "https://api.openai.com/v1/decisions"
MODEL = "gpt-6-luna"


class DecisionsError(RuntimeError):
    """비밀이나 공급자 응답 본문을 포함하지 않는 오류."""


def read_api_key(path: Path = ROOT / ".env", environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    values = {}
    if path.is_symlink():
        raise DecisionsError(".env는 심볼릭 링크가 아닌 일반 파일이어야 합니다.")
    if path.exists():
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
            raise DecisionsError(".env 파일 권한을 600으로 설정하세요: chmod 600 .env")
        values = dotenv_values(path, interpolate=False)
    key = env.get("OPENAI_API_KEY", values.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise DecisionsError("루트 .env에 OPENAI_API_KEY를 입력하세요.")
    return key


def validate_request(payload: dict) -> None:
    if not isinstance(payload, dict) or payload.get("model") != MODEL:
        raise DecisionsError(f"요청 model은 {MODEL}이어야 합니다.")
    if not isinstance(payload.get("input"), (str, list)) or not payload["input"]:
        raise DecisionsError("input에 텍스트 또는 메시지 배열을 지정하세요.")
    questions = payload.get("questions")
    if not isinstance(questions, list) or not 1 <= len(questions) <= 200:
        raise DecisionsError("questions는 1~200개 질문의 배열이어야 합니다.")
    for question in questions:
        if not isinstance(question, dict) or question.get("type") not in {"predicate", "choice", "score"}:
            raise DecisionsError("질문 type은 predicate, choice, score 중 하나여야 합니다.")
        if not isinstance(question.get("instructions"), str) or not question["instructions"].strip():
            raise DecisionsError("질문마다 instructions를 지정하세요.")
        field = {"choice": "choices", "score": "levels"}.get(question["type"])
        if field and (not isinstance(question.get(field), list) or not question[field]):
            raise DecisionsError(f"{question['type']} 질문에는 {field} 배열이 필요합니다.")


def create_decision(payload: dict, api_key: str, *, transport=None) -> dict:
    validate_request(payload)
    if not api_key.strip():
        raise DecisionsError("OPENAI_API_KEY가 비어 있습니다.")
    # 고정 공식 endpoint, 자동 retry/redirect 없음. 모의 transport는 테스트용이다.
    with httpx.Client(timeout=60, follow_redirects=False, transport=transport) as client:
        try:
            response = client.post(ENDPOINT, json=payload, headers={"Authorization": f"Bearer {api_key}"})
        except httpx.RequestError:
            raise DecisionsError("API 연결 실패 또는 시간 초과. 자동 재시도하지 않았습니다.") from None
    if not response.is_success:
        hints = {401: "API 키를 확인하세요.", 403: "계정/프로젝트의 모델 접근 권한을 확인하세요.",
                 404: "Decisions API/모델의 계정 제공 여부를 확인하세요.",
                 429: "API 사용 한도와 결제 상태를 확인하세요."}
        raise DecisionsError(f"OpenAI HTTP {response.status_code}. " + hints.get(response.status_code, "요청 형식 또는 공급자 상태를 확인하세요."))
    try:
        result = response.json()
    except ValueError:
        raise DecisionsError("API가 JSON 응답을 반환하지 않았습니다.") from None
    if not isinstance(result, dict) or not isinstance(result.get("answers"), list):
        raise DecisionsError("API 응답에 answers 배열이 없습니다.")
    return result
