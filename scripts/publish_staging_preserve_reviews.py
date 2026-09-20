#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import publish_staging

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'data'/'manifest.json'

def main():
    before=json.loads(MANIFEST.read_text(encoding='utf-8'))
    reviews=before.get('weekly_reviews',[])
    publish_staging.main()
    after=json.loads(MANIFEST.read_text(encoding='utf-8'))
    after['weekly_reviews']=reviews
    MANIFEST.write_text(json.dumps(after,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'Preserved {len(reviews)} existing weekly review entries')
if __name__=='__main__': main()
