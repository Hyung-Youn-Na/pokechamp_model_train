"""무외부호출: 저장 v6 JSON을 후보별 요약 입력으로 변환한다."""
import argparse
import hashlib
import json
from pathlib import Path

from .rules import identity
from .summary import PROFILE, decorate, remove_summaries


def main():
    parser=argparse.ArgumentParser(description='v6 후보에 현재 대면 요약 추가 (모델/API 호출 없음)')
    parser.add_argument('--input',type=Path,required=True,help='원 v6 state/questions JSON')
    parser.add_argument('--output',type=Path,required=True,help='새 출력 JSON; 기존 파일 덮어쓰기 금지')
    parser.add_argument('--format',choices=['v6','openai'],default='v6')
    args=parser.parse_args()
    source=args.input.read_bytes();base=json.loads(source)
    result=decorate(base)
    if remove_summaries(result)!=base:raise ValueError('base input was changed')
    if args.format=='openai':
        from integration.openai_decisions_battle.core import to_request,from_request
        body=to_request(result)
        if from_request(body)!=result:raise ValueError('OpenAI transform lost data')
    else:body=result
    args.output.parent.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(body,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    provenance=args.output.with_suffix(args.output.suffix+'.provenance.json')
    if args.output.exists() or provenance.exists():raise FileExistsError('output/provenance already exists')
    with args.output.open('x') as stream:stream.write(encoded)
    record=dict(profile=PROFILE,base_version=base['state']['version'],format=args.format,
        source=str(args.input.resolve()),source_sha256=hashlib.sha256(source).hexdigest(),
        output_sha256=hashlib.sha256(encoded.encode()).hexdigest(),rules=identity(),
        base_preserved=True,model_calls=0)
    with provenance.open('x') as stream:json.dump(record,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(output=str(args.output),provenance=str(provenance),model_calls=0),ensure_ascii=False))


if __name__=='__main__':main()
