#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import publish_staging
from weekly_review_contract import normalise_weekly_reviews

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'data'/'manifest.json'
STAGING=ROOT/'data'/'staging'

def main():
    before=json.loads(MANIFEST.read_text(encoding='utf-8'))
    existing=normalise_weekly_reviews(before.get('weekly_reviews',[]))
    staged_meta=json.loads((STAGING/'public.json').read_text(encoding='utf-8'))
    staged=normalise_weekly_reviews(staged_meta.get('weekly_reviews',[]))
    publish_staging.main()
    after=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if staged:
        replacements={(item.get('season'),item.get('week')) for item in staged}
        merged=[item for item in existing if (item.get('season'),item.get('week')) not in replacements]
        merged.extend(staged)
        merged.sort(key=lambda item:(item.get('season',0),item.get('week',0),item.get('as_of','')))
        after['weekly_reviews']=merged
    else:
        after['weekly_reviews']=existing
    MANIFEST.write_text(json.dumps(after,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'Published {len(after.get("weekly_reviews",[]))} weekly review entries')
if __name__=='__main__':
    main()
