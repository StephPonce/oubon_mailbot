"""
Thin compatibility wrapper to expose amazon_paapi.AmazonApi under the
python_amazon_paapi module name expected by the app/tests.
"""

from amazon_paapi import AmazonApi  # re-export for backwards compatibility

__all__ = ["AmazonApi"]
