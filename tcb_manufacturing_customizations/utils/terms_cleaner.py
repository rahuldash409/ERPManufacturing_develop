import frappe
import re
from html import unescape

@frappe.whitelist()
def clean_terms_html(html_content):
    """
    Clean HTML content from terms field to remove unwanted elements
    and keep only essential formatting
    """
    if not html_content:
        return ""
    
    try:
        # Remove div containers with scroll/overflow styles
        html_content = re.sub(r'<div[^>]*(?:overflow\s*:\s*(?:auto|scroll|hidden))[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<div[^>]*(?:height\s*:\s*\d+px)[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<div[^>]*(?:border\s*:\s*1px\s+solid)[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<div[^>]*(?:width\s*:\s*99\.9%)[^>]*>', '', html_content, flags=re.IGNORECASE)
        
        # Remove any style attributes with overflow, scroll, border, height, width
        html_content = re.sub(r'style="[^"]*(?:overflow|scroll|border|height|width)[^"]*"', '', html_content, flags=re.IGNORECASE)
        
        # Remove table structures completely (including content wrapping)
        html_content = re.sub(r'</?(?:table|tbody|thead|tfoot)[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<tr[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</tr>', '<br>', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</?(?:td|th)[^>]*>', '', html_content, flags=re.IGNORECASE)
        
        # Remove font tags but keep content
        html_content = re.sub(r'</?font[^>]*>', '', html_content, flags=re.IGNORECASE)
        
        # Remove span tags but keep content
        html_content = re.sub(r'</?span[^>]*>', '', html_content, flags=re.IGNORECASE)
        
        # Convert div tags to line breaks
        html_content = re.sub(r'</div>\s*<div[^>]*>', '<br>', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</?div[^>]*>', '', html_content, flags=re.IGNORECASE)
        
        # Clean up multiple consecutive line breaks
        html_content = re.sub(r'(<br[^>]*>\s*){3,}', '<br><br>', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'(<br[^>]*>\s*){2}', '<br><br>', html_content, flags=re.IGNORECASE)
        
        # Remove leading and trailing breaks
        html_content = re.sub(r'^(\s*<br[^>]*>\s*)+', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'(\s*<br[^>]*>\s*)+$', '', html_content, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        html_content = re.sub(r'\s+', ' ', html_content)
        html_content = html_content.strip()
        
        # Convert &nbsp; to regular spaces
        html_content = html_content.replace('&nbsp;', ' ')
        
        # Unescape HTML entities
        html_content = unescape(html_content)
        
        return html_content
        
    except Exception as e:
        frappe.log_error(f"Error cleaning terms HTML: {str(e)}")
        # Fallback: return plain text if cleaning fails
        return re.sub(r'<[^>]+>', '', html_content)


def get_cleaned_terms(doctype, docname, fieldname="terms"):
    """
    Helper function to get cleaned terms for a specific document
    """
    try:
        doc = frappe.get_doc(doctype, docname)
        terms_content = getattr(doc, fieldname, "")
        return clean_terms_html(terms_content)
    except Exception as e:
        frappe.log_error(f"Error getting cleaned terms: {str(e)}")
        return ""


# Alternative function if you want to pass the document directly
@frappe.whitelist()
def clean_document_terms(doc, fieldname="terms"):
    import json
    """
    Clean terms directly from document object
    """
    doc= json.loads(doc)
    terms_content = doc.get(fieldname, "")
    return clean_terms_html(terms_content)