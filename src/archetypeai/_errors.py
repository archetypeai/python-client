
class ApiError(Exception):
    def __init__(self, api_error):
        super().__init__(api_error)
        if isinstance(api_error, dict) and "errors" in api_error:
            self.errors = api_error["errors"]
        else:
            self.errors = None
    
    def validate_error_code_exists(self, error_code: str) -> bool:
        """Validates that at least one instance of the error code exists."""
        if self.errors is None:
            return False
        for error in self.errors:
            code = error.get("code", None)
            if code == error_code:
                return True
        return False
    
    def validate_error_count(self, error_count: int) -> bool:
        """Validates the number of expected error messages match the count."""
        if self.errors is None:
            return False
        return len(self.errors) == error_count