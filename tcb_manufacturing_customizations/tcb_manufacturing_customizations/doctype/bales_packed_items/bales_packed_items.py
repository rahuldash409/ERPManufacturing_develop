# Copyright (c) 2026, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BalesPackedItems(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		batch_no: DF.Link | None
		item_code: DF.Link | None
		item_name: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		qty: DF.Float
		sub_batch: DF.Data | None
		warehouse: DF.Link | None
	# end: auto-generated types

	pass
