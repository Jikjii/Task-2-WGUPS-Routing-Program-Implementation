# Student ID: 000000000 | WGUPS Routing Program | C950 Data Structures and Algorithms II, Task 2
"""
main.py - Entry point for the WGUPS Routing Program.

PROGRAM FLOW
------------
1. SETTINGS     The constants below (city, trucks, drivers, capacity, speed, start of
                day, mileage limit, known address corrections) describe the Salt
                Lake City scenario. Another city edits these settings and replaces the
                three CSV files in data/. The routing code itself does not change.
2. LOAD DATA    data_loader.py reads packages.csv into the custom ChainingHashTable
                (key = package ID), then reads the locations and distance matrix.
3. PLAN & RUN   routing.py loads the trucks, dispatches them with the two drivers,
                and orders each truck's stops with the nearest-neighbor heuristic as
                it leaves. Every package gets a departure time and a delivery time.
4. VALIDATE     validation.py re-checks the finished day against the scenario rules
                and returns [PASS]/[FAIL] results, which this file prints with the
                total mileage.
5. INTERFACE    A menu lets the supervisor see the status of ONE package or ALL
                packages (grouped by truck) at ANY time of day, with the miles driven
                so far and the total for all trucks, plus an end-of-day route report.

The whole day is simulated once at start-up. Every status question afterwards is
answered from the recorded timestamps (departure and delivery times), so a status at
9:00 AM and a status at 1:00 PM always come from the same consistent plan.

Run interactively:            python main.py
Print one report and exit:    python main.py --time 9:00
                              python main.py --time 12:30 PM
                              python main.py --package 9 --time 10:30
                              python main.py --summary
"""

import os
import sys

from data_loader import load_distance_table, load_packages
from package import (AddressCorrection, STATUS_AT_HUB, STATUS_DELAYED,
                     STATUS_DELIVERED, STATUS_EN_ROUTE)
from routing import run_delivery_day
from time_utils import clock_time, format_time, parse_time
from truck import Truck
from validation import validate_day

# ------------------------------------------------------------------------- settings
CITY_NAME = "Salt Lake City"
DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PACKAGE_FILE = os.path.join(DATA_FOLDER, "packages.csv")
ADDRESS_FILE = os.path.join(DATA_FOLDER, "addresses.csv")
DISTANCE_FILE = os.path.join(DATA_FOLDER, "distances.csv")

NUMBER_OF_TRUCKS = 3
NUMBER_OF_DRIVERS = 2
TRUCK_CAPACITY = 16           # packages per truck
TRUCK_SPEED_MPH = 18          # average speed, delivery time already factored in
DAY_START = clock_time(8, 0)  # drivers leave the hub no earlier than 8:00 AM
MILEAGE_LIMIT = 140           # combined miles for all trucks must stay under this

# Package 9's listed address is wrong. WGUPS learns the correct address at 10:20 AM.
ADDRESS_CORRECTIONS = [
    AddressCorrection(package_id=9, effective_time=clock_time(10, 20),
                      address="410 S State St", city="Salt Lake City",
                      state="UT", zip_code="84111"),
]

WIDTH = 118                   # every report line fits in 118 columns
TABLE_LINE = "-" * WIDTH
HEAVY_LINE = "=" * WIDTH
TIME_PROMPT = "Enter a time (e.g. 9:00 AM, 1:05 PM, or 24-hour 13:05): "


# --------------------------------------------------------------------- the day plan
def build_day():
    """Load the data and simulate the whole delivery day. Returns everything the UI needs."""
    package_table = load_packages(PACKAGE_FILE, ADDRESS_CORRECTIONS)
    distance_table = load_distance_table(ADDRESS_FILE, DISTANCE_FILE)

    trucks = []
    for truck_number in range(1, NUMBER_OF_TRUCKS + 1):
        trucks.append(Truck(truck_number, TRUCK_CAPACITY, TRUCK_SPEED_MPH))

    run_delivery_day(package_table, distance_table, trucks, NUMBER_OF_DRIVERS, DAY_START)
    checks = validate_day(package_table, trucks, NUMBER_OF_DRIVERS, DAY_START, MILEAGE_LIMIT)
    return package_table, trucks, checks


def total_miles_at(trucks, query_time):
    """Combined miles all trucks have driven by `query_time`."""
    return sum(truck.miles_at(query_time) for truck in trucks)


def total_miles(trucks):
    """Combined miles all trucks drive over the whole day."""
    return sum(truck.total_miles for truck in trucks)


def deadline_label(package):
    """'EOD', or the deadline shown in the same format as every other time."""
    return "EOD" if package.deadline is None else format_time(package.deadline)


# ------------------------------------------------------------- look-up function (B)
def lookup_package(package_table, package_id, query_time):
    """
    LOOK-UP FUNCTION: take a package ID and return each of its data components at
    `query_time`:
        (delivery address, delivery deadline, delivery city, delivery zip code,
         package weight, delivery status including the delivery time)
    Returns None if the package ID does not exist. Average O(1) thanks to the hash table.
    """
    package = package_table.lookup(package_id)
    if package is None:
        return None
    address, city, _state, zip_code = package.address_at(query_time)
    _status, status_text = package.status_at(query_time)
    return address, deadline_label(package), city, zip_code, package.weight, status_text


# ------------------------------------------------------------------------ reports (D)
def print_banner(trucks, checks):
    """Start-up summary: every rule check, the total mileage, and each truck's day."""
    print(HEAVY_LINE)
    print(f"WGUPS ROUTING PROGRAM - {CITY_NAME} daily local deliveries".center(WIDTH))
    print(HEAVY_LINE)
    print("Constraint check for the planned day:")
    for check in checks:
        print(f"  {check}")
    all_passed = all(check.passed for check in checks)
    print(TABLE_LINE)
    print(f"Result: {'ALL CONSTRAINTS MET' if all_passed else 'SOME CONSTRAINTS FAILED'} | "
          f"Total mileage traveled by all trucks: {total_miles(trucks):.1f} miles")
    for truck in trucks:
        if truck.departure_time is None:
            print(f"  Truck {truck.truck_id}: not used today (no packages)")
            continue
        print(f"  Truck {truck.truck_id}: {truck.total_miles:5.1f} miles | driver {truck.driver_id} | "
              f"left hub {format_time(truck.departure_time)} | "
              f"{'back at hub' if truck.returns_to_hub else 'last delivery'} "
              f"{format_time(truck.end_time)} | {len(truck.package_ids)} packages")
    print(HEAVY_LINE)


def print_all_packages(package_table, trucks, query_time):
    """Status of every package, grouped by the truck it is loaded on, at query_time."""
    print()
    print(HEAVY_LINE)
    print(f"STATUS OF ALL PACKAGES AT {format_time(query_time)}".center(WIDTH))
    print(HEAVY_LINE)
    status_order = [STATUS_DELAYED, STATUS_AT_HUB, STATUS_EN_ROUTE, STATUS_DELIVERED]
    counts = [0, 0, 0, 0]
    footnotes = []
    for truck in trucks:
        print(f"TRUCK {truck.truck_id} | Driver {truck.driver_id} | {truck.status_at(query_time)} | "
              f"Miles driven so far: {truck.miles_at(query_time):.1f} of {truck.total_miles:.1f}")
        print(TABLE_LINE)
        print(f"{'ID':>3}  {'Delivery Address':<39}{'City':<18}{'Zip':<7}{'Deadline':<10}"
              f"{'Kg':>4}  Delivery Status")
        print(TABLE_LINE)
        for package_id in sorted(truck.package_ids):
            package = package_table.lookup(package_id)
            address, deadline, city, zip_code, weight, status_text = lookup_package(
                package_table, package_id, query_time)
            status, _ = package.status_at(query_time)
            counts[status_order.index(status)] += 1
            if package.correction is not None and query_time < package.correction.effective_time:
                address = address + " *"
                footnotes.append(
                    f"* Package {package_id}: wrong address listed. WGUPS receives the corrected "
                    f"address at {format_time(package.correction.effective_time)}.")
            print(f"{package_id:>3}  {address:<39}{city:<18}{zip_code:<7}{deadline:<10}"
                  f"{weight:>4}  {status_text}")
        print()
    for note in footnotes:
        print(note)
    print(TABLE_LINE)
    print(f"Summary at {format_time(query_time)}: {counts[3]} delivered, {counts[2]} en route, "
          f"{counts[1]} at the hub, {counts[0]} delayed")
    print(f"Total mileage traveled by all trucks at {format_time(query_time)}: "
          f"{total_miles_at(trucks, query_time):.1f} miles "
          f"(end of day total: {total_miles(trucks):.1f} miles)")
    print(HEAVY_LINE)


def print_one_package(package_table, trucks, package_id, query_time):
    """Every data component of one package at query_time, via the look-up function."""
    result = lookup_package(package_table, package_id, query_time)
    if result is None:
        keys = package_table.keys()
        print(f"\nPackage {package_id} was not found. Valid IDs are {keys[0]}-{keys[-1]}.")
        return
    address, deadline, city, zip_code, weight, status_text = result
    package = package_table.lookup(package_id)
    print()
    print(f"PACKAGE {package_id} AT {format_time(query_time)}")
    print("-" * 70)
    print(f"  Delivery address : {address}")
    if package.correction is not None:
        fix_time = format_time(package.correction.effective_time)
        if query_time < package.correction.effective_time:
            print(f"                     (wrong address listed - WGUPS receives the corrected "
                  f"address at {fix_time})")
        else:
            print(f"                     (corrected at {fix_time}; originally listed as "
                  f"{package.listed_address}, {package.listed_zip_code})")
    print(f"  Delivery city    : {city}")
    print(f"  Delivery zip code: {zip_code}")
    print(f"  Delivery deadline: {deadline}")
    print(f"  Package weight   : {weight} kg")
    print(f"  Delivery status  : {status_text}")
    print(f"  Assigned truck   : {package.truck_id}")
    if package.notes:
        print(f"  Special note     : {package.notes}")
    print("-" * 70)
    print(f"  Total mileage traveled by all trucks at {format_time(query_time)}: "
          f"{total_miles_at(trucks, query_time):.1f} miles")


def print_final_report(package_table, trucks, checks):
    """End-of-day report: every truck's route, stop by stop, plus the total mileage."""
    print()
    print(HEAVY_LINE)
    print("END OF DAY ROUTE REPORT".center(WIDTH))
    print(HEAVY_LINE)
    for truck in trucks:
        if truck.departure_time is None:
            print(f"TRUCK {truck.truck_id} | not used today (no packages)")
            print()
            continue
        print(f"TRUCK {truck.truck_id} | Driver {truck.driver_id} | {len(truck.package_ids)} packages | "
              f"route: {truck.route_strategy} | {truck.total_miles:.1f} miles")
        print(TABLE_LINE)
        for stop in truck.stops:
            label = ", ".join(f"#{pid}" for pid in stop.package_ids) or "(hub)"
            place = f"{stop.address} ({stop.location_name})"
            print(f"  {format_time(stop.arrival_time)}  {stop.miles_so_far:6.1f} mi  "
                  f"{place[:72]:<72}{label}")
        print()
    all_delivered = all(p.delivery_time is not None for p in package_table.values())
    all_passed = all(check.passed for check in checks)
    print(TABLE_LINE)
    print(f"All {len(package_table)} packages delivered: {'yes' if all_delivered else 'NO'} | "
          f"All constraints met: {'yes' if all_passed else 'NO'}")
    print(f"TOTAL MILEAGE TRAVELED BY ALL TRUCKS: {total_miles(trucks):.1f} miles "
          f"(limit {MILEAGE_LIMIT} miles)")
    print(HEAVY_LINE)


# ----------------------------------------------------------------- user interface (D)
def ask_for_time(prompt):
    """Keep asking until the user types a valid time such as 9:00 AM or 13:15."""
    while True:
        text = input(prompt).strip()
        try:
            return parse_time(text)
        except ValueError as error:
            print(f"  {error}")


def ask_for_package_id(package_table):
    """Keep asking until the user types the ID of a package that exists."""
    keys = package_table.keys()
    while True:
        text = input(f"Enter a package ID ({keys[0]}-{keys[-1]}): ").strip()
        if text.isdecimal() and len(text) <= 6 and int(text) in package_table:
            return int(text)
        print(f"  '{text}' is not a valid package ID.")


def run_menu(package_table, trucks, checks):
    """
    The supervisor's main loop: 1 = all packages by truck at a time, 2 = one package
    at a time, 3 = end-of-day route report and total mileage, 4 = exit.
    """
    while True:
        print()
        print("What would you like to see?")
        print("  1. Status of ALL packages at a given time (grouped by truck, with mileage)")
        print("  2. Status of ONE package at a given time")
        print("  3. End-of-day route report and total mileage")
        print("  4. Exit")
        choice = input("Choose 1-4: ").strip()
        if choice == "1":
            print_all_packages(package_table, trucks, ask_for_time(TIME_PROMPT))
        elif choice == "2":
            package_id = ask_for_package_id(package_table)
            print_one_package(package_table, trucks, package_id, ask_for_time(TIME_PROMPT))
        elif choice == "3":
            print_final_report(package_table, trucks, checks)
        elif choice == "4":
            print("Goodbye.")
            return
        else:
            print("  Please choose 1, 2, 3 or 4.")


def run_command_line(arguments, package_table, trucks, checks):
    """
    Non-interactive mode, used for the status screenshots. Returns 0 on success, or 1
    if the arguments were not valid.
    """
    usage = ("Usage: python main.py [--time TIME [--package ID]] | [--summary]\n"
             "  TIME examples: 9:00, 10:30, 13:05, \"1:05 PM\" or 1:05pm")
    if arguments == ["--summary"]:
        print_banner(trucks, checks)
        print_final_report(package_table, trucks, checks)
        return 0

    query_time = None
    package_id = None
    position = 0
    while position < len(arguments):
        flag = arguments[position]
        if flag not in ("--time", "--package") or position + 1 >= len(arguments):
            print(f"Unexpected or incomplete option '{flag}'.\n{usage}")
            return 1
        value = arguments[position + 1]
        position += 2
        if flag == "--time":
            # Allow an unquoted AM/PM, e.g.  --time 1:05 PM
            if position < len(arguments) and arguments[position].lower() in ("am", "pm"):
                value = value + " " + arguments[position]
                position += 1
            try:
                query_time = parse_time(value)
            except ValueError as error:
                print(error)
                return 1
        else:
            if not value.isdecimal() or len(value) > 6:
                print(f"'{value}' is not a valid package ID.")
                return 1
            package_id = int(value)

    if query_time is None:
        print(f"Please add a time.\n{usage}")
        return 1
    if package_id is None:
        print_all_packages(package_table, trucks, query_time)
    else:
        print_one_package(package_table, trucks, package_id, query_time)
    return 0


def main():
    """Simulate the day once, then answer questions from the menu or the command line."""
    try:
        package_table, trucks, checks = build_day()
    except (OSError, ValueError, KeyError) as error:
        # A missing file, an unreadable value, or an impossible load: explain and stop.
        print(f"Could not plan the delivery day: {error}")
        return 1

    arguments = sys.argv[1:]
    if arguments:
        return run_command_line(arguments, package_table, trucks, checks)

    print_banner(trucks, checks)
    try:
        run_menu(package_table, trucks, checks)
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
