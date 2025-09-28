"""
Enhanced fillpdf module with subfield support
基于fillpdf库，增强了对特殊子字段结构的支持
"""

from .enhanced_fillpdfs import get_form_fields, write_fillable_pdf

__version__ = "1.0.0-enhanced"
__all__ = ["get_form_fields", "write_fillable_pdf"] 