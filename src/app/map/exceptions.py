class UnsupportedExtensionError(Exception):
    """Exception when file extension differs from .txt or .json"""
    pass

class InvalidMapContentError(Exception):
    """Exception when the content of the file does not follow the rules"""
    pass