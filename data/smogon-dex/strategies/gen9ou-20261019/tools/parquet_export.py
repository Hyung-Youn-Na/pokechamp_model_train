"""Typed flat columns; nested source fields remain lossless JSON strings."""
import argparse,json
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from collect import write

def export(root):
    checks=[];schemas={}
    for name in ('pokemon','strategies','sets','sections','issues'):
        rows=json.loads((root/f'{name}.json').read_text())
        keys=sorted({k for row in rows for k in row})
        nested={k for k in keys if any(isinstance(row.get(k),(list,dict)) for row in rows)}
        columns={k:k+'_json' if k in nested else k for k in keys}
        assert len(set(columns.values()))==len(columns)
        converted=[{columns[k]:json.dumps(row[k],ensure_ascii=False) if k in nested and row.get(k) is not None else row.get(k) for k in keys} for row in rows]
        table=pa.Table.from_pylist(converted)
        pq.write_table(table,root/f'{name}.parquet',compression='zstd')
        back=pq.read_table(root/f'{name}.parquet').to_pylist()
        assert back==converted
        for original,saved in zip(rows,back):
            for k,value in original.items():
                actual=saved[columns[k]]
                if k in nested and actual is not None:actual=json.loads(actual)
                assert actual==value,(name,k)
        schemas[name]=dict(columns=columns,json_encoded_fields=sorted(nested),rows=len(rows))
        checks.append(dict(table=name,rows=len(rows),all_original_fields_roundtrip=True))
    write(root/'parquet-schema.json',schemas)
    write(root/'parquet-validation.json',dict(passed=True,tables=checks))
    print(json.dumps(checks))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();export(a.output)
