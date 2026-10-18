"""
data_loader.py - Reads the WGUPS CSV files and builds the program's data structures.

    data/packages.csv   -> Package objects stored in a ChainingHashTable (key = package ID)
    data/addresses.csv  -> the list of delivery locations (row 0 is the hub)
    data/distances.csv  -> the lower-triangular distance matrix, mirrored to a full matrix

The CSV files hold the data from the "WGUPS Package File" and "WGUPS Distance Table"
spreadsheets. The street text in addresses.csv was matched to the package file, because
a package's address must match its location's address to find its distances (case
and extra spaces are ignored). The spreadsheet itself spells some addresses two ways,
such as "5383 S 900 East #104" and "5383 South 900 East #104". To run the program for
another city, replace the three CSV files and adjust the settings at the top of
main.py (trucks, drivers, start time, mileage limit, known address corrections). The
routing code itself does not change.
"""

import csv

from distance_table import DistanceTable
from hash_table import ChainingHashTable
from package import Package


def load_packages(package_csv_path, address_corrections):
    """
    Read every package into the hash table.

    address_corrections is a list of AddressCorrection objects (known fixes, such as
    package 9's corrected address at 10:20 AM). Each one is attached to its package.

    Time complexity: O(n) for n packages (each hash-table insert is O(1) on average).
    """
    package_table = ChainingHashTable()

    with open(package_csv_path, newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        next(reader)  # skip the header row
        for row in reader:
            if not row or not row[0].strip():
                continue  # ignore blank lines at the end of the file
            package = Package(
                package_id=int(row[0]),
                address=row[1].strip(),
                city=row[2].strip(),
                state=row[3].strip(),
                zip_code=row[4].strip(),
                deadline_text=row[5].strip(),
                weight=row[6].strip(),
                notes=row[7].strip() if len(row) > 7 else "",
            )
            # INSERTION: the package ID is the key. The Package object holds the address,
            # deadline, city, zip code, weight, and delivery status (with delivery time).
            package_table.insert(package.package_id, package)

    for correction in address_corrections:
        package = package_table.lookup(correction.package_id)
        if package is not None:
            package.set_address_correction(correction)

    return package_table


def load_distance_table(address_csv_path, distance_csv_path):
    """
    Read the locations and the triangular distance matrix, then mirror the triangle so
    that matrix[i][j] == matrix[j][i] for every pair.

    Time complexity: O(L^2) for L locations, done once at start-up.
    """
    location_names = []
    location_addresses = []
    with open(address_csv_path, newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        next(reader)  # header
        for row in reader:
            if not row:
                continue
            location_names.append(row[1].strip())
            location_addresses.append(row[2].strip())

    size = len(location_addresses)
    matrix = []
    for _ in range(size):
        matrix.append([0.0] * size)

    with open(distance_csv_path, newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        next(reader)  # header
        row_number = 0
        for row in reader:
            if not row:
                continue
            # Column 0 is the row label. The rest is the triangle: only columns up to
            # and including the diagonal are filled in.
            for column_number in range(row_number + 1):
                cell = row[column_number + 1].strip()
                miles = float(cell) if cell else 0.0
                matrix[row_number][column_number] = miles
                matrix[column_number][row_number] = miles  # same distance both ways
            row_number += 1

    if row_number != size:
        raise ValueError(f"distances.csv has {row_number} rows but addresses.csv has {size}.")

    return DistanceTable(location_names, location_addresses, matrix)
