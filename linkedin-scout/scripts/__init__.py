"""
q4 - High-Performance Native CDP Extraction Pipeline
"""

from .schemas import LinkedInContact, SearchCluster, OutreachRecord
from .cdp_interceptor import parse_voyager_json, capture_voyager_traffic
from .dom_parser import parse_linkedin_search_html
from .entity_matcher import score_role, score_company, rank_and_filter_contacts
from .pipeline_db import NetworkDatabase

__all__ = [
    "LinkedInContact",
    "SearchCluster",
    "OutreachRecord",
    "parse_voyager_json",
    "capture_voyager_traffic",
    "parse_linkedin_search_html",
    "score_role",
    "score_company",
    "rank_and_filter_contacts",
    "NetworkDatabase",
]
