from datetime import datetime


def _merge(x):
    """Concatenate an ID back together."""

    p = x['FACILITYID']['prefix']
    i = x['FACILITYID']['str_id']
    return p + i


def _get_values(rows: list, field: str) -> list:
    """An internal function for returning all values of a particular
    column of the table."""

    values = [r[field] for r in rows]
    return values


class Edit:
    """A class meant to be used once a table has been slated for edits.

    Parameters
    ----------
    rows : list
        A list of dictionaries, where each dict represents a row of the
        table
    duplicates : list
        A list of GLOBALIDs that have duplicated FACILITYIDs
    prefix : str
        The correct prefix for the layer
    geom_type : str
        The type of geometry being evaluated. None if evaluating a table

    Attributes
    ----------
    used : list
        A reverse sorted list of used IDs in the table
    unused : list
        A reverse sorted list of unused IDs between the min and max of
        used IDs
    edited : list
        A list of dicts, where each dict represents a row that has had
        its FACILITYID changed.
    """
    def __init__(self, rows, duplicates, prefix, geom_type):
        self.rows = rows
        self.duplicates = duplicates
        self.prefix = prefix
        self.geom_type = geom_type
        self.used = self.get_used()
        self.unused = self.get_unused()
        self.edited = list()

    def get_used(self):
        """Extracts a list of used ids in rows, sorted in reverse order.

        Returns
        -------
        list
            Used IDs between min and max utilized IDs
        """
        all_used = sorted(
            [x["FACILITYID"]["int_id"]
             for x in self.rows if x["FACILITYID"]["int_id"] is not None],
            reverse=True)
        return all_used

    def get_unused(self) -> list:
        """Extracts a list of unused ids that lie between the minimum
        and maximum ids in order to backfill gaps in ID sequences.

        Returns
        -------
        list
            Unused IDs between the minimum and maximum utilized IDs
        """

        min_id = self.used[-1]

        # initiate a try block in case the max id is too large to compute a set
        # and overflows computer memory
        for m in self.used:
            try:
                set_of_all = set(range(min_id, m))
                set_of_used = set(self.used)
                unused = sorted(list(set_of_all - set_of_used), reverse=True)
                break
            except (OverflowError, MemoryError):
                continue

        return unused

    def get_new_id(self) -> int:
        """Finds the next best ID to apply to a row with missing or
        duplicated IDs.

        This function modifies both inputs by either popping the last
        item off the end of the unused list or incrementing the used
        list by 1

        Parameters
        ----------
        used : list
            A list of used IDs in the table, sorted in reverse order.
        unused : list
            A list of unused IDs between the minimum and maximum IDs in
            the feature class, sorted in reverse order.

        Returns
        -------
        int
            An integer number representing the next logical ID to assign
        """

        if self.unused:
            new_id = self.unused.pop()
        else:
            max_id = self.used[0] + 1
            new_id = max_id
            self.used.insert(0, max_id)

        return new_id

    def duplicate_sorter(self, x):
        """A function meant to be used in the builtin sort function for
        lists.

        Dynamically sorts the lists of duplicates based on the shape
        type of the feature class in question.

        Parameters
        ----------
        x : dict
            Represents a single row from the list of rows

        Returns
        -------
        tuple
            A tuple that dictates how to multi-sort
        """

        # Define date to replace Null values in the sort
        # Null values first, followed byt oldest to newest
        _null_date = datetime(1400, 1, 1)

        def geom_sorter(g):
            """Determines the proper field to sort on based
            on the spatial data type."""

            if g == 'Polygon':
                return - x['SHAPE@'].area
            elif g == 'Polyline':
                return - x['SHAPE@'].length
            else:
                return (x['CREATED_DATE'] or _null_date)

        sort_1 = _merge(x)
        sort_2 = geom_sorter(self.geom_type)
        sort_3 = (x['LAST_EDITED_DATE'] or _null_date)

        return (sort_1, sort_2, sort_3)

    def edit(self):
        """Iterates through a list of rows, editing incorrect or
        duplicated entries along the way.

        This method edits duplicated FACILITYIDs first, followed by
        incorrect or missing FACILITYIDs. It also modifies the following
        attributes of the class: rows, used, unused, and edited.
        Ultimately the edited attribute will be populated if edits were
        made to the table.

        The method knows to edit incorrect IDs based on the following
        criteria:

        Prefix is not capitalized
        Prefix of the row does not exist
        Prefix does not equal the layer's designated prefix
        The ID does not exist
        The ID has leading zeros
        The ID has already been used
        """

        if self.duplicates:
            # Identify rows that contain duplicate FACILITYIDs with the correct
            # prefix
            dup_rows = [row for row in self.rows if row['GLOBALID']
                        in self.duplicates and row['FACILITYID']['prefix']
                        == self.prefix]
            # Perform the sort
            dup_rows.sort(key=self.duplicate_sorter)
            # Iterate through each unique ID in the duplicated rows
            distinct = set([_merge(r) for r in dup_rows])
            for i in distinct:
                chunk = [x for x in dup_rows if _merge(x) == i]
                # The last ID of the list (e.g. 'chunk[-1]'), does not need to
                # be edited, since all of its dupes have been replaced
                for c in chunk[:-1]:
                    # Modify 'rows' input at Class instantiation so that they
                    # are not inspected later on
                    edit_row = self.rows.pop(self.rows.index(c))
                    new_id = self.get_new_id()
                    edit_row["FACILITYID"]["int_id"] = new_id
                    edit_row["FACILITYID"]["str_id"] = str(new_id)
                    self.edited.append(edit_row)

        while self.rows:
            edit_row = self.rows.pop(0)
            # Flag whether edits need to be made to the row
            # Assume no edits to start
            edits = False
            pfix = edit_row["FACILITYID"]["prefix"]
            str_id = edit_row["FACILITYID"]["str_id"]
            int_id = edit_row["FACILITYID"]["int_id"]

            # PREFIX EDITS
            if not pfix or not pfix.isupper() or pfix != self.prefix:
                edit_row["FACILITYID"]["prefix"] = self.prefix
                edits = True

            # ID EDITS
            tests = [not str_id, len(str_id) != len(str(int_id)),
                     int_id in self.used]
            if any(tests):
                new_id = self.get_new_id()
                edit_row["FACILITYID"]["int_id"] = new_id
                edit_row["FACILITYID"]["str_id"] = str(new_id)
                edits = True

            if edits:
                self.edited.append(edit_row)