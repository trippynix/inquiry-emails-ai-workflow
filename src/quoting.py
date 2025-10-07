import json
from typing import Dict, Any, List, Optional

class QuoteGenerator:
    """
    Generates a deterministic price quote from a parsed email event.

    It applies pricing, bulk discounts, and category discounts based on
    pre-defined rules. If the parsed event contains gaps, it marks the
    quote as pending.
    """
    def __init__(self, price_list: Dict[str, Any], discount_rules: Dict[str, Any]):
        if not price_list or not discount_rules:
            raise ValueError("Price list and discount rules cannot be empty.")
        self.price_list = price_list
        self.discount_rules = discount_rules
        self.tax_rate = discount_rules.get("tax_rate_percent", 0) / 100.0

    def generate_quote(self, parsed_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrates the quote generation process.

        Args:
            parsed_event: The structured data extracted from an email.

        Returns:
            A dictionary representing the final quote, either complete or pending.
        """
        email_id = parsed_event["email_id"]
        gaps = parsed_event.get("gaps_identified", [])

        # If there are any gaps, the quote cannot be generated.
        if gaps or not self._is_quotable(parsed_event["extracted_items"]):
            return {
                "quote_id": email_id,
                "status": "pending",
                "pending_reason": "One or more items could not be identified or are missing quantities.",
                "gaps": gaps,
                "line_items": [],
                "summary": {}
            }

        # --- If no gaps, proceed with calculation ---
        line_items = self._calculate_line_items(parsed_event["extracted_items"])
        summary = self._calculate_summary(line_items)

        return {
            "quote_id": email_id,
            "status": "success",
            "line_items": line_items,
            "summary": summary
        }

    def _is_quotable(self, items: List[Dict[str, Any]]) -> bool:
        """Checks if all extracted items are valid for quoting."""
        if not items:
            return False
        return all(item.get("product_name") and item.get("quantity") for item in items)

    def _calculate_line_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculates totals and discounts for each line item."""
        calculated_items = []
        for item in items:
            product_name = item["product_name"]
            quantity = item["quantity"]
            product_info = self.price_list.get(product_name)

            if not product_info:
                continue # Should not happen if _is_quotable passed, but as a safeguard.

            unit_price = product_info["price"]
            category = product_info["category"]
            subtotal = unit_price * quantity

            # Apply discounts sequentially
            bulk_discount_percent = self._get_bulk_discount(quantity)
            category_discount_percent = self.discount_rules["category_discount"].get(category, 0)
            
            bulk_discount_amount = subtotal * (bulk_discount_percent / 100.0)
            post_bulk_total = subtotal - bulk_discount_amount
            
            category_discount_amount = post_bulk_total * (category_discount_percent / 100.0)
            
            total_discount = bulk_discount_amount + category_discount_amount
            final_price = subtotal - total_discount
            
            calculated_items.append({
                "product_name": product_name,
                "quantity": quantity,
                "unit_price": unit_price,
                "subtotal": subtotal,
                "total_discount_applied": total_discount,
                "final_price": final_price
            })
        return calculated_items

    def _get_bulk_discount(self, quantity: int) -> float:
        """Finds the applicable bulk discount percentage for a given quantity."""
        applicable_discount = 0
        # The rules should be sorted by min_quantity descending to find the best match
        sorted_rules = sorted(self.discount_rules["bulk_discount"], key=lambda x: x["min_quantity"], reverse=True)
        for rule in sorted_rules:
            if quantity >= rule["min_quantity"]:
                applicable_discount = rule["discount_percent"]
                break
        return applicable_discount

    def _calculate_summary(self, line_items: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculates the overall quote summary (subtotal, tax, total)."""
        grand_subtotal = sum(item["subtotal"] for item in line_items)
        total_discount = sum(item["total_discount_applied"] for item in line_items)
        net_total = grand_subtotal - total_discount
        tax_amount = net_total * self.tax_rate
        grand_total = net_total + tax_amount
        
        return {
            "grand_subtotal": round(grand_subtotal, 2),
            "total_discount": round(total_discount, 2),
            "net_total_before_tax": round(net_total, 2),
            "tax_amount": round(tax_amount, 2),
            "grand_total": round(grand_total, 2)
        }
