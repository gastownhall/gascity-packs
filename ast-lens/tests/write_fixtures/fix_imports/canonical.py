import os


def describe() -> str:
    """Use os; leave sys and OrderedDict unused so the importer drops them.

    Imports are also written out of canonical order (sys before os), so a
    correct importer must both remove the unused names and sort the rest.
    """
    return os.getcwd()
