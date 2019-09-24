from arcpy import ListFields, ExecuteError, GetCount_management
from os import path


class FacilityID:
    """A class intended to deal with the specifics of controlling for the quality of Facility IDs. This builds upon the
    Describe object in arcpy."""
    def __init__(self, iterator_path):
        self.full_path = path.join(*iterator_path)
        self.fields = [f.name for f in ListFields(self.full_path) if not f.required]
        self.prefix = self.find_prefix()

    def has_records(self):
        """Determines if there are any records in the feature class to analyze."""
        try:
            count = int(GetCount_management(self.full_path).getOutput(0))
            return True if count >= 1 else False
        except ExecuteError:
            # TODO: Add info logging describing an error in retrieving a feature count
            return None

    def has_facilityid(self):
        """Determines if the feature class has the FACILITYID field."""
        return True if "FACILITYID" in self.fields else False

    def has_globalid(self):
        """Determines if the feature class has the GLOBALID field."""
        return True if "GLOBALID" in self.fields else False

    def find_prefix(self):
        """Determines the prefix of the feature class based on the most prevalent occurrence."""
        # TODO: fill in code
        return True