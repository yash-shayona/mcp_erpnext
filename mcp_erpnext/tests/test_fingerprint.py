from __future__ import annotations

import unittest

from mcp_erpnext.services.common.fingerprint import stable_fingerprint


class StableFingerprintTests(unittest.TestCase):
	def test_ignored_path_is_not_business_state(self):
		base = {"delivery_note": {"posting_time": "10:00:00", "grand_total": 500}}
		changed_time = {"delivery_note": {"posting_time": "10:00:01", "grand_total": 500}}
		self.assertEqual(
			stable_fingerprint(
				base, ignored_paths={("delivery_note", "posting_time")}
			),
			stable_fingerprint(
				changed_time, ignored_paths={("delivery_note", "posting_time")}
			),
		)

	def test_material_field_and_row_order_remain_fingerprinted(self):
		base = {"items": [{"item_code": "A"}, {"item_code": "B"}], "total": 500}
		changed_total = {"items": [{"item_code": "A"}, {"item_code": "B"}], "total": 600}
		reordered = {"items": [{"item_code": "B"}, {"item_code": "A"}], "total": 500}
		self.assertNotEqual(stable_fingerprint(base), stable_fingerprint(changed_total))
		self.assertNotEqual(stable_fingerprint(base), stable_fingerprint(reordered))


if __name__ == "__main__":
	unittest.main()
