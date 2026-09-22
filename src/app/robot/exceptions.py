from src.app.robot.schemas import CleanReport

class NoMapLoadedError(Exception):
    """Exception when cleaning task is requested but no map is laoded"""
    pass

class InvalidStartCoordinateError(Exception):
    """Exception when starting coordinates are outside the map or not walkable"""
    pass

class CollisionError(Exception):
    """Exception when there is a collision or the robot goes outside the map. Report the collision.
    """
    def __init__(self, report: CleanReport):
        """Attach the session's report, which becomes the response body."""
        super().__init__("Collision occurred during cleaning session.")
        self.report = report