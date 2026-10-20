"""python -m integration.openai_decisions"""

import argparse
import json
import sys
from pathlib import Path

from .client import DecisionsError, create_decision, read_api_key, validate_request


def main() -> int:
    parser = argparse.ArgumentParser(description="gpt-6-luna Decisions API 호출 (기본: predicate 예제 1회)")
    parser.add_argument("--request", type=Path, help="전송할 JSON 파일; 생략하면 predicate 예제")
    parser.add_argument("--dry-run", action="store_true", help="키를 읽거나 API를 호출하지 않고 요청 출력")
    args = parser.parse_args()
    try:
        request_path = args.request or Path(__file__).parent / "examples" / "predicate.json"
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        validate_request(payload)
        if args.dry_run:
            result = payload
        else:
            result = create_decision(payload, read_api_key())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except DecisionsError as error:
        print(f"오류: {error}", file=sys.stderr)
    except (OSError, UnicodeError, ValueError):
        print("오류: 입력/설정 파일을 읽을 수 없거나 JSON/문자 형식이 올바르지 않습니다.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
