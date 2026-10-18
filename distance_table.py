"""
distance_table.py - Distances between every pair of delivery locations.

The WGUPS Distance Table spreadsheet is a lower-triangular matrix: the distance from
location A to location B is written only once, because it is the same in both
directions. data_loader.load_distance_table mirrors that triangle into a full square
matrix (a list of lists), and this class stores it, so any distance is a single O(1)
list access: matrix[from][to].

Addresses are turned into matrix row numbers with the program's own ChainingHashTable
(no built-in dictionary), so finding a location is also O(1) on average.
"""

from hash_table import ChainingHashTable


def normalize_address(address):
    """Compare addresses case-insensitively and ignore extra spaces."""
    return " ".join(address.lower().split())


class DistanceTable:
    """Holds every delivery location and the mileage between any two of them."""

    def __init__(self, location_names, location_addresses, matrix):
        self.location_names = location_names          # e.g. "Council Hall"
        self.location_addresses = location_addresses  # e.g. "300 State St"
        self.matrix = matrix                          # matrix[i][j] = miles from i to j

        # Address -> row number look-up table built with the custom hash table.
        self.address_index = ChainingHashTable(len(location_addresses))
        for index in range(len(location_addresses)):
            self.address_index.insert(normalize_address(location_addresses[index]), index)

    @property
    def hub_index(self):
        """Row 0 of the WGUPS Distance Table is the hub (Western Governors University)."""
        return 0

    @property
    def hub_address(self):
        return self.location_addresses[self.hub_index]

    def index_of(self, address):
        """Return the matrix row for an address. Raise a clear error if it is unknown."""
        index = self.address_index.lookup(normalize_address(address))
        if index is None:
            raise KeyError(f"Address '{address}' is not in the WGUPS Distance Table.")
        return index

    def distance_between(self, address_a, address_b):
        """Miles between two street addresses. O(1)."""
        return self.matrix[self.index_of(address_a)][self.index_of(address_b)]

    def name_of(self, address):
        """The location's friendly name, e.g. '410 S State St' -> 'Third District Juvenile Court'."""
        return self.location_names[self.index_of(address)]
