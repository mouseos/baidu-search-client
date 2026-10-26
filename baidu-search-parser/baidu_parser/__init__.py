"""baidu_parser — structured extraction from Baidu APK (wise) search HTML."""

from .parser import PARSER_VERSION, parse_search_results

__all__ = ["parse_search_results", "PARSER_VERSION"]
__version__ = PARSER_VERSION
