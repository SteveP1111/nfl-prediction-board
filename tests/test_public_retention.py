from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publish_staging import compact_completed_week_catalogue


class PublicRetentionTests(unittest.TestCase):
    def test_completed_weeks_keep_one_latest_snapshot(self):
        catalogue=[
            {"id":"w1-a","season":2026,"week":1,"capturedAt":"2026-09-10T05:00:00+01:00"},
            {"id":"w1-b","season":2026,"week":1,"capturedAt":"2026-09-11T15:00:00+01:00"},
            {"id":"w2-a","season":2026,"week":2,"capturedAt":"2026-09-17T05:00:00+01:00"},
            {"id":"w2-b","season":2026,"week":2,"capturedAt":"2026-09-20T05:00:00+01:00"},
            {"id":"w3-a","season":2026,"week":3,"capturedAt":"2026-09-22T05:00:00+01:00"},
            {"id":"w3-b","season":2026,"week":3,"capturedAt":"2026-09-22T15:00:00+01:00"},
        ]
        result=compact_completed_week_catalogue(catalogue,[])
        self.assertEqual([x["id"] for x in result],["w1-b","w2-b","w3-b"])

    def test_final_review_can_select_authoritative_snapshot(self):
        catalogue=[
            {"id":"w2-authoritative","season":2026,"week":2,"capturedAt":"2026-09-19T05:00:00+01:00"},
            {"id":"w2-later","season":2026,"week":2,"capturedAt":"2026-09-20T05:00:00+01:00"},
            {"id":"w3-current","season":2026,"week":3,"capturedAt":"2026-09-22T05:00:00+01:00"},
        ]
        reviews=[{
            "season":2026,"week":2,"review_scope":"game_lines_final",
            "authoritative_snapshot_id":"w2-authoritative"
        }]
        result=compact_completed_week_catalogue(catalogue,reviews)
        self.assertEqual([x["id"] for x in result],["w2-authoritative","w3-current"])


if __name__=="__main__":
    unittest.main()
