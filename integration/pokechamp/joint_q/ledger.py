"""One logical result per (observation, action, replicate, source version)."""
from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path
from .storage import VERSION, atomic, canonical, digest, read, rollout_seeds, sha


class Ledger:
    def __init__(self,directory,source_id):
        self.directory=Path(directory)
        self.rollout_seeds = rollout_seeds
        if (self.directory/'manifest.json').exists():
            from .tera_config import seed_function
            self.rollout_seeds = seed_function(read(self.directory/'manifest.json'))
        self.db=sqlite3.connect(self.directory/'rollouts.sqlite',timeout=60)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, observation_id TEXT NOT NULL,
            action_id TEXT NOT NULL, replicate INTEGER NOT NULL CHECK(replicate BETWEEN 0 AND 31),
            root_path TEXT NOT NULL, root_sha256 TEXT NOT NULL, game_id TEXT NOT NULL,
            source_id TEXT NOT NULL, seeds TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0, result_path TEXT, result_sha256 TEXT,
            UNIQUE(observation_id,action_id,replicate,source_id));
          CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(observation_id,replicate,action_id)
            WHERE status IN ('pending','retry') AND attempts<3;
          CREATE TABLE IF NOT EXISTS attempts (job_id TEXT NOT NULL, attempt INTEGER NOT NULL,
            started REAL NOT NULL, finished REAL, status TEXT NOT NULL, error TEXT,
            result_path TEXT, result_sha256 TEXT, PRIMARY KEY(job_id,attempt));
          CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, at REAL NOT NULL,
            kind TEXT NOT NULL, job_id TEXT, detail TEXT NOT NULL);
        ''')
        self.source_id=source_id
        with self.db:
            found=self.db.execute("SELECT value FROM metadata WHERE key='source_id'").fetchone()
            if found and found[0]!=source_id:
                raise ValueError('ledger source version mismatch; explicit whole-observation recovery required')
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('source_id',?)",(source_id,))
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('started_at',?)",(str(time.time()),))

    def event(self,kind,job_id=None,**detail):
        self.db.execute('INSERT INTO events(at,kind,job_id,detail) VALUES (?,?,?,?)',
                        (time.time(),kind,job_id,json.dumps(detail)))

    def register(self,root,game_id):
        with self.db:
            for a in root['actions']:
                for r in range(32):
                    oid=root['observation_id']
                    jid=digest([oid,a['action_id'],r,self.source_id])
                    values=(jid,oid,a['action_id'],r,root['path'],root['sha256'],game_id,self.source_id,
                            json.dumps(self.rollout_seeds(oid,r),sort_keys=True))
                    existing=self.db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
                    if existing:
                        if tuple(existing[k] for k in ('id','observation_id','action_id','replicate','root_path',
                                      'root_sha256','game_id','source_id','seeds'))!=values:
                            raise ValueError('logical rollout identity collision')
                        continue
                    self.db.execute('INSERT INTO jobs(id,observation_id,action_id,replicate,root_path,'
                                    'root_sha256,game_id,source_id,seeds) VALUES (?,?,?,?,?,?,?,?,?)',values)

    def claim(self,job_id=None):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            sql="SELECT * FROM jobs WHERE status IN ('pending','retry') AND attempts<3"
            row=self.db.execute(sql+(' AND id=?' if job_id else '')+' ORDER BY observation_id,replicate,action_id LIMIT 1',
                                (job_id,) if job_id else ()).fetchone()
            if row is None:
                return None
            attempt=row['attempts']+1
            self.db.execute("UPDATE jobs SET status='running',attempts=? WHERE id=?",(attempt,row['id']))
            self.db.execute('INSERT INTO attempts(job_id,attempt,started,status) VALUES (?,?,?,?)',
                            (row['id'],attempt,time.time(),'running'))
            self.event('claim',row['id'],attempt=attempt)
            return dict(row)|dict(attempt=attempt)

    def finish(self,job_id,attempt,path):
        path=Path(path)
        result=read(path)
        row=self.db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not row or result['job_id']!=job_id or result['attempt']!=attempt or result['source_id']!=self.source_id:
            raise ValueError('result identity/version mismatch')
        if result['root_sha256']!=row['root_sha256'] or result['seeds']!=json.loads(row['seeds']):
            raise ValueError('result root/seed mismatch')
        outcome=result['status']
        if outcome not in {'win','draw','loss','error','interrupted'}:
            raise ValueError('invalid result status')
        if outcome in {'win','draw','loss'}:
            if not result.get('terminal') or result.get('score')!={'win':1,'draw':.5,'loss':0}[outcome]:
                raise ValueError('nonterminal result cannot become a label')
        checksum=sha(path)
        name=str(path.relative_to(self.directory))
        with self.db:
            if row['status']=='complete':
                if row['result_sha256']!=checksum or row['result_path']!=name:
                    raise ValueError('conflicting completed logical rollout')
                self.event('duplicate_result',job_id,attempt=attempt)
                return
            if row['attempts']!=attempt or row['status']!='running':
                raise ValueError('stale result attempt')
            status='complete' if outcome in {'win','draw','loss'} else 'retry' if attempt<3 else 'failed'
            self.db.execute('UPDATE jobs SET status=?,result_path=?,result_sha256=? WHERE id=?',
                            (status,name,checksum,job_id))
            self.db.execute('UPDATE attempts SET finished=?,status=?,error=?,result_path=?,result_sha256=? '
                            'WHERE job_id=? AND attempt=?',
                            (time.time(),outcome,result.get('error'),name,checksum,job_id,attempt))
            self.event('result',job_id,attempt=attempt,status=outcome,resumed=result.get('resumed',False),
                       elapsed_seconds=result.get('elapsed_seconds'))

    def recover(self):
        for row in self.db.execute("SELECT * FROM jobs WHERE status='running'").fetchall():
            path=self.directory/'private/results'/f"{row['id']}-a{row['attempts']}.json.gz"
            if path.exists():
                self.finish(row['id'],row['attempts'],path)
                continue
            with self.db:
                status='retry' if row['attempts']<3 else 'failed'
                self.db.execute('UPDATE jobs SET status=? WHERE id=?',(status,row['id']))
                self.db.execute("UPDATE attempts SET status='interrupted',finished=?,error=? WHERE job_id=? AND attempt=?",
                    (time.time(),'coordinator/worker interrupted before atomic result',row['id'],row['attempts']))
                self.event('recover',row['id'],attempt=row['attempts'],status=status)
        # A previously committed result must still exist with the exact bytes.
        for row in self.db.execute("SELECT * FROM jobs WHERE status='complete'"):
            if sha(self.directory/row['result_path'])!=row['result_sha256']:
                raise ValueError('committed result missing or corrupted: '+row['id'])

    def counts(self):
        return dict(self.db.execute('SELECT status,count(*) FROM jobs GROUP BY status').fetchall())

    def close(self):
        self.db.close()
