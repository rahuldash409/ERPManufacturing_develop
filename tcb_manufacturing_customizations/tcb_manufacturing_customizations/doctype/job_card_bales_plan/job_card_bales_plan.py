# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class JobCardBalesPlan(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bale_number: DF.Int
		bale_qty: DF.Float
		batch_no: DF.Link | None
		batch_qty_used: DF.Float
		item_name: DF.Data | None
		packed_item: DF.Link | None
		packaging_item: DF.Link | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		sub_batch: DF.Data | None
	# end: auto-generated types

	pass
