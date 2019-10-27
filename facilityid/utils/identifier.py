import os

from arcpy import ArcSDESQLExecute, Describe, ExecuteError, GetCount_management, ListFields
from arcpy.da import SearchCursor


class Identifier:
    """A class intended to deal with the specifics of controlling for the quality of Facility IDs. 
    This class inherits the functionality of the arcpy.Describe function.
    """

    def __init__(self, tuple_path):
        self.tuple_path = tuple_path
        self.full_path = os.path.join(*self.tuple_path)
        self.fields = [f.name for f in ListFields(
            self.full_path) if not f.required]
        self.connection = self.tuple_path[0]
        self.dataset = self.tuple_path[1] if len(
            self.tuple_path) == 3 else None
        self.owner, self.name = tuple_path[-1].split(".")
        self.prefix = self.find_prefix()

        self._desc = Describe(self.full_path)

    def __getattr__(self, item):
        """Pass any other attribute or method calls through to the underlying Describe object"""
        return getattr(self._desc, item)

    def has_records(self) -> bool:
        """Determines if there are any records in the feature class to analyze."""
        try:
            count = int(GetCount_management(self.full_path).getOutput(0))
            return True if count >= 1 else False
        except ExecuteError:
            # TODO: Add info logging describing an error in retrieving a feature count
            return None

    def has_facilityid(self) -> bool:
        """Determines if the feature class has the FACILITYID field.

        :return: Boolean
        """
        return True if "FACILITYID" in self.fields else False

    def has_globalid(self) -> bool:
        """Determines if the feature class has the GLOBALID field.

        :return: Boolean, True if the SDE item has a GLOBALID field
        """
        return True if "GLOBALID" in self.fields else False

    def has_table(self) -> bool:
        """Identifies whether an item in the SDE is a feature class or table

        :return: Boolean, true if the item is a feature class or table
        """
        return True if self._desc.datasetType in ['FeatureClass', 'Table'] else False

    def find_prefix(self):
        """Determines the prefix of the feature class based on the most prevalent occurrence."""
        if self.has_facilityid():
            # Initialize an executor object for SDE
            execute_object = ArcSDESQLExecute(self.connection)
            query_name = ".".join([self.owner, self.name[:26]]) + "_EVW" if self.isVersioned else ".".join(
                [self.owner, self.name[:30]])
            query = f"""SELECT REGEXP_SUBSTR(FACILITYID, '^[a-zA-Z]+') as PREFIXES,
                    COUNT(*) as PFIXCOUNT
                    FROM {query_name}
                    GROUP BY REGEXP_SUBSTR(FACILITYID, '^[a-zA-Z]+')
                    ORDER BY PFIXCOUNT DESC
                    FETCH FIRST ROW ONLY"""
            try:
                result = execute_object.execute(query)
                return result[0]
            except (ExecuteError, TypeError, AttributeError):
                return None
        else:
            return None
        # TODO: pickle and shelve list of prefixes after every script run

    def get_rows(self):
        """Opens an arcpy SearchCursor and records fields relevant to the QC of FACILITYID

        :return: List, rows represented as dictionaries within a list
        """
        fields = ['GLOBALID', 'FACILITYID', 'CREATED_USER',
                  'CREATED_DATE', 'LAST_EDITED_USER', 'LAST_EDITED_DATE']
        if self.datasetType == 'FeatureClass':
            fields.append('SHAPE@')
        row_list = []
        with SearchCursor(self.full_path, fields) as search:
            for row in search:
                row_list.append({fields[i]: row[i] for i in range(len(fields))})
        return row_list

    def can_gisscr_edit(self, connection) -> bool:
        """Reveals if the feature class is editable through the GISSCR connection.

        :param connection: File path to an SDE connection with the GISSCR user
        :return: Boolean
        """
        query = """SELECT PRIVILEGE
                   FROM ALL_TAB_PRIVS
                   WHERE TABLE_NAME = '{table}'
                   AND TABLE_SCHEMA = '{owner}'""".format(table=self.name.upper(), owner=self.owner.upper())
        execute_object = ArcSDESQLExecute(connection)
        result = execute_object.execute(query)
        editable = False  # Assume GISSCR user cannot edit by default
        for row in result:
            if row[0] in ("UPDATE", "INSERT", "DELETE"):
                editable = True
                break
        return editable


"""
Here are all the reasons an ID would need to be edited:

1) No prefix
2) No number
3) Prefix not capitalized
4) Prefix not equal to the layer's designated prefix
5) Number has leading zeros
6) NULL
7) Duplicated

Preconditions to check before script run:

ESSENTIALS:
1) Make sure the item is a table or feature class (STOP if not)
2) GLOBALID and FACILITYID fields are present (STOP if not)
3) Make sure some FACILITYIDs already exist (STOP if not)

NON ESSENTIALS:
4) Make sure the item is versioned (CONTINUE regardless)
5) Check if GISSCR can edit (CONTINUE either way)
6) Check that Editor Tracking is turned on (CONTINUE either way)
"""
