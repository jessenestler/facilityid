import os
from arcpy.da import Walk
from arcpy.mp import ArcGISProject
from arcpy import DeleteVersion_management, ListVersions


# Define globals specific to these functions
aprx_location = "./EditFacilityID.aprx"


def find_in_sde(sde_path: str = None, *args) -> list:
    """ Finds all possible feature classes within the sde connection provided based on a list of pattern matches, and
    returns a list representing that file path broken into [sde, dataset (if it exists), feature class]. For example,
    the requester might only want to find the path of feature classes that contain "wF", "sw", and "Flood". If no
    patterns are provided, the function will return the path of everything in SDE.

    :param sde_path: The file path to the sde connection file
    :param args: A list of optional strings to filter the data
    :return: A list consisting of [root_directory, dataset, feature_name]
    """
    walker = Walk(sde_path, ['FeatureDataset', 'FeatureClass'])
    for directory, folders, files in walker:
        for f in files:
            if args and any(arg in f for arg in args):
                if directory.endswith(".sde"):
                    item = [directory, None, f]
                else:
                    dataset = directory.split(os.sep).pop()
                    item = [directory[:-(1 + len(dataset))], dataset, f]
                yield item
    del walker


def delete_facilityid_versions(connection: str = None) -> None:
    """Deletes versions created for editing Facility IDs

    :param connection: location of the sde connection file
    :return: None
    """
    del_versions = [v for v in ListVersions(connection) if "FacilityID" in v]
    for d in del_versions:
        DeleteVersion_management(connection, d)


# TODO: verify that add_layer_to_map works
def add_layer_to_map(feature_class_name: str = None) -> None:
    """ Adds the input layer to a .aprx Map based on the owner of the data.
    For example, the UTIL.wFitting feature would be added to the "UTIL" map
    in the designated .aprx

    :param feature_class_name: Name of the feature class inside sde
    :return:
    """
    user, fc = feature_class_name.split(".")
    aprx = ArcGISProject(aprx_location)
    user_map = aprx.listMaps("%s" % user)[0]
    user_map.addDataFromPath()  # TODO: add data from the gisscr user
    aprx.save()
