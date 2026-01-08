"""Amazon Product Advertising API connector."""

from .amazon_paapi import AmazonPAAPIConnector

# Alias for backward compatibility
AmazonPAAPI = AmazonPAAPIConnector

__all__ = ['AmazonPAAPIConnector', 'AmazonPAAPI']
