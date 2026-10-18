"""
routing.py - Decides which truck carries each package, when each truck leaves, and
the order of its stops. This file holds the core algorithm.

THE ALGORITHM, IN THREE STEPS
-----------------------------
1. LOAD THE TRUCKS (constraint-aware greedy loading)
   a. Packages that "must be delivered with" each other are joined into one bundle
      (a union-find over package IDs). A bundle always rides on one truck.
   b. Bundles are loaded most-constrained first, in this order:
        1) a required truck ("Can only be on truck 2")   -> that truck
        2) delayed ("will not arrive until 9:05 am")      -> the LATE truck, which
                                                             waits at the hub for them
        3) a wrong address that is fixed later in the day -> the SECOND-WAVE truck,
                                                             which leaves after the fix
        4) any other delivery deadline (earliest first)   -> the EARLY truck
        5) end-of-day (EOD)                               -> see (c)
      If the preferred truck is full, or could not reach a deadline in time even by
      driving straight from the hub, the next truck in the list is used.
   c. EOD bundles are placed by a self-adjusting "nearest cluster" rule. Each round,
      the unplaced bundle closest (in miles) to any known address already on a truck
      with room goes onto that truck. An empty truck is measured from the hub. Ties go
      to the lower package ID, then the lower truck number. Packages for the same or
      a nearby address therefore tend to share a truck while it has room.

2. DISPATCH THE TRUCKS (only as many trucks on the road as there are drivers)
   Trucks with the most urgent deadline go first, then trucks that are ready
   earliest. A truck is "ready" once every package on it is at the hub with a
   known address: 9:05 AM for the delayed packages, 10:20 AM for package 9. If no
   driver is free, the truck waits for the driver who can get back to the hub
   soonest. That driver's current truck drives back to the hub. Every other truck
   ends the day at its last stop, because the day ends when the last package is
   delivered.

3. ORDER THE STOPS (nearest-neighbor heuristic), done for each truck as it leaves
   Starting at the hub, the truck always drives to the closest address it still has
   packages for, and drops off every package for that address at once. This greedy
   heuristic is self-adjusting: each choice depends on where the truck is now.
   Three variants are tried for every truck:
        - plain nearest neighbor
        - deadline-first nearest neighbor (any stop with a deadline package first)
        - earliest-deadline-first nearest neighbor (the most urgent deadline first)
   The shortest variant that delivers every package on time is kept. Routing
   happens inside dispatch, because the deadline checks need the truck's departure
   time and package 9's corrected address.

LIMITS: each truck makes one trip, so a day holds at most trucks x capacity
packages (3 x 16 = 48 here). Route variants are compared on one-way miles, because
whether a truck must drive back to the hub is decided later, when another truck
needs its driver.

COMPLEXITY (n packages, B bundles, k packages on one truck, T trucks, D drivers)
   Bundling O(n log n) | Loading O(B * n^2) | Routing O(k^2) per truck |
   Dispatch O(T * D + n) -> overall O(n^3) in the worst case, instant for 40 packages.
"""

from package import STATUS_DELIVERED, STATUS_EN_ROUTE
from time_utils import travel_time
from truck import RouteStop

NO_DEADLINE = float("inf")  # used to sort EOD packages after every real deadline


# --------------------------------------------------------------------------- bundles
def build_bundles(package_table):
    """
    Join packages that must travel together into bundles, using union-find.

    "Must be delivered with" is transitive. Package 14 goes with 15 and 19, 16 with 13
    and 19, and 20 with 13 and 15, so 13, 14, 15, 16, 19 and 20 must all share one
    truck. Union-find merges these groups. The parent links are kept in a plain list
    indexed by package ID (no dictionary). Returns a list of bundles, each a sorted
    list of package IDs, ordered by their lowest package ID.
    """
    package_ids = package_table.keys()
    largest_id = package_ids[-1] if package_ids else 0
    parent = list(range(largest_id + 1))

    def find(package_id):
        # Follow parent links to the group's root, shortening the path as we go.
        while parent[package_id] != package_id:
            parent[package_id] = parent[parent[package_id]]
            package_id = parent[package_id]
        return package_id

    def union(first_id, second_id):
        root_a, root_b = find(first_id), find(second_id)
        if root_a != root_b:
            parent[max(root_a, root_b)] = min(root_a, root_b)  # lowest ID becomes the root

    for package_id in package_ids:
        for partner_id in package_table.lookup(package_id).bundle_ids:
            if partner_id in package_table:
                union(package_id, partner_id)

    # Collect the members of each group (list of lists, indexed by root ID).
    members_by_root = []
    for _ in range(largest_id + 1):
        members_by_root.append([])
    for package_id in package_ids:
        members_by_root[find(package_id)].append(package_id)
    return [members for members in members_by_root if members]


# --------------------------------------------------------------- bundle/truck facts
def _earliest_deadline(package_ids, package_table):
    """The earliest deadline among the packages, in seconds (NO_DEADLINE if all are EOD)."""
    earliest = NO_DEADLINE
    for package_id in package_ids:
        deadline = package_table.lookup(package_id).deadline
        if deadline is not None and deadline.total_seconds() < earliest:
            earliest = deadline.total_seconds()
    return earliest


def _ready_time(package_ids, package_table, day_start):
    """The earliest time ALL these packages can leave the hub (delays, address fixes)."""
    ready = day_start
    for package_id in package_ids:
        package_ready = package_table.lookup(package_id).earliest_ready_time(day_start)
        if package_ready > ready:
            ready = package_ready
    return ready


def _bundle_required_truck(bundle, package_table):
    """The truck number a bundle is restricted to, or None. Conflicts are an error."""
    required = None
    for package_id in bundle:
        truck_number = package_table.lookup(package_id).required_truck
        if truck_number is not None:
            if required is not None and required != truck_number:
                raise ValueError(f"Bundle {bundle} is restricted to two different trucks.")
            required = truck_number
    return required


def _bundle_has(bundle, package_table, test):
    """True if any package in the bundle passes `test`."""
    for package_id in bundle:
        if test(package_table.lookup(package_id)):
            return True
    return False


def _can_take(truck, bundle, package_table, distance_table, day_start):
    """
    A truck can take a bundle if it has room AND, with the bundle on board, every
    deadline package it would carry could still make its deadline by driving straight
    from the hub at the truck's ready time. (A real route can only be slower, so this
    check rules out hopeless choices. It does not promise a feasible route.)
    """
    if not truck.has_room_for(len(bundle)):
        return False
    combined = truck.package_ids + bundle
    leaves_at = _ready_time(combined, package_table, day_start)
    for package_id in combined:
        package = package_table.lookup(package_id)
        if package.deadline is None:
            continue
        arrival = leaves_at
        if _known_address(package) is not None:
            miles = distance_table.distance_between(distance_table.hub_address, package.address)
            arrival = leaves_at + travel_time(miles, truck.speed_mph)
        if arrival > package.deadline:
            return False
    return True


def _choose_truck(preferred_trucks, bundle, package_table, distance_table, day_start):
    """
    The first truck in preference order that can take the bundle. If none passes the
    deadline check, fall back to the first one with room. The validation report then
    shows exactly which deadline is at risk, instead of the program stopping.
    """
    for truck in preferred_trucks:
        if _can_take(truck, bundle, package_table, distance_table, day_start):
            return truck
    for truck in preferred_trucks:
        if truck.has_room_for(len(bundle)):
            return truck
    raise ValueError(f"No truck has room for bundle {bundle}.")


def _known_address(package):
    """
    The address to plan around while loading at the start of the day. A package whose
    listed address is known to be wrong has no usable address yet, so it is skipped.
    """
    if package.has_wrong_address or package.correction is not None:
        return None
    return package.address


def _distance_to_truck(bundle, truck, package_table, distance_table):
    """
    How close a bundle is to a truck's current load: the shortest distance from any
    bundle address to any known address on the truck. If the truck has no known
    addresses yet, distance is measured from the hub.
    """
    anchors = []
    for loaded_id in truck.package_ids:
        address = _known_address(package_table.lookup(loaded_id))
        if address is not None:
            anchors.append(address)
    if not anchors:
        anchors.append(distance_table.hub_address)

    best = NO_DEADLINE
    for package_id in bundle:
        bundle_address = _known_address(package_table.lookup(package_id))
        if bundle_address is None:
            continue
        for anchor in anchors:
            miles = distance_table.distance_between(anchor, bundle_address)
            if miles < best:
                best = miles
    return best


# --------------------------------------------------------------------------- loading
def load_trucks(package_table, distance_table, trucks, day_start):
    """
    Step 1 of the algorithm: assign every package to a truck (see the module docstring).

    trucks[0] is the EARLY truck (leaves first), trucks[1] the LATE truck (waits for
    delayed packages), and trucks[-1] the SECOND-WAVE truck (leaves when a driver
    returns, once any address corrections are known).
    """
    early_truck = trucks[0]
    late_truck = trucks[1] if len(trucks) > 1 else trucks[0]
    second_wave_truck = trucks[-1]

    def truck_number(number):
        for truck in trucks:
            if truck.truck_id == number:
                return truck
        raise ValueError(f"A package requires truck {number}, but there is no such truck.")

    # Sort every bundle into the FIRST category it matches (most constrained first).
    required_bundles, delayed_bundles, correction_bundles = [], [], []
    deadline_bundles, end_of_day_bundles = [], []
    for bundle in build_bundles(package_table):
        if _bundle_required_truck(bundle, package_table) is not None:
            required_bundles.append(bundle)
        elif _bundle_has(bundle, package_table, lambda p: p.hub_arrival_time is not None):
            delayed_bundles.append(bundle)
        elif _bundle_has(bundle, package_table,
                         lambda p: p.correction is not None or p.has_wrong_address):
            correction_bundles.append(bundle)
        elif _bundle_has(bundle, package_table, lambda p: p.deadline is not None):
            deadline_bundles.append(bundle)
        else:
            end_of_day_bundles.append(bundle)

    # 1) Required trucks are not negotiable, so they are loaded first.
    for bundle in required_bundles:
        target = truck_number(_bundle_required_truck(bundle, package_table))
        if not target.has_room_for(len(bundle)):
            raise ValueError(f"Truck {target.truck_id} is too full for required bundle {bundle}.")
        target.load(bundle)

    # 2) Delayed bundles ride the late truck, which simply waits for them at the hub.
    for bundle in delayed_bundles:
        _choose_truck([late_truck, second_wave_truck, early_truck],
                      bundle, package_table, distance_table, day_start).load(bundle)

    # 3) Wrong-address bundles ride the second-wave truck, which leaves after the fix.
    for bundle in correction_bundles:
        _choose_truck([second_wave_truck, late_truck, early_truck],
                      bundle, package_table, distance_table, day_start).load(bundle)

    # 4) Deadline bundles: most urgent first (bigger bundles first on a tie), onto the
    #    truck that leaves earliest and still has room.
    deadline_bundles.sort(key=lambda b: (_earliest_deadline(b, package_table), -len(b), b[0]))
    for bundle in deadline_bundles:
        _choose_truck([early_truck, late_truck, second_wave_truck],
                      bundle, package_table, distance_table, day_start).load(bundle)

    # 5) EOD bundles: each round, place the bundle closest to any truck with room.
    while end_of_day_bundles:
        best_bundle, best_truck, best_miles = None, None, None
        for bundle in end_of_day_bundles:
            for truck in trucks:
                if not truck.has_room_for(len(bundle)):
                    continue
                miles = _distance_to_truck(bundle, truck, package_table, distance_table)
                if best_miles is None or miles < best_miles:
                    best_bundle, best_truck, best_miles = bundle, truck, miles
        if best_bundle is None:
            raise ValueError("The trucks are full: there are more packages than "
                             "trucks x capacity, and each truck makes one trip.")
        best_truck.load(best_bundle)
        end_of_day_bundles.remove(best_bundle)


# --------------------------------------------------------------------------- routing
class _PlannedStop:
    """A stop in a candidate route, before the route is chosen and committed."""

    def __init__(self, address, arrival_time, miles_so_far, package_ids):
        self.address = address
        self.arrival_time = arrival_time
        self.miles_so_far = miles_so_far
        self.package_ids = package_ids


def _nearest_neighbor_route(package_ids, package_table, distance_table, departure_time,
                            speed_mph, priority):
    """
    Build one candidate route with the nearest-neighbor heuristic.

    From the current location, drive to the closest address that still has packages
    waiting, and deliver every package for that address in one stop. `priority`
    limits which packages may be chosen next:
        "none"     - any remaining package
        "deadline" - only packages with a deadline, until none are left
        "earliest" - only packages sharing the earliest remaining deadline

    Returns (stops, total_miles, late_package_ids). Nothing on the packages is changed.
    """
    remaining = list(package_ids)
    current_address = distance_table.hub_address
    current_time = departure_time
    miles = 0.0
    stops = []
    late = []

    while remaining:
        # Which packages may we choose from right now?
        candidates = remaining
        if priority != "none":
            earliest = _earliest_deadline(remaining, package_table)
            if earliest != NO_DEADLINE:
                candidates = []
                for package_id in remaining:
                    deadline = package_table.lookup(package_id).deadline
                    if deadline is None:
                        continue
                    if priority == "deadline" or deadline.total_seconds() == earliest:
                        candidates.append(package_id)

        # Greedy choice: the closest candidate address. Ties go to the earlier deadline,
        # then the lower package ID, so the result is the same every run.
        best_id, best_key = None, None
        for package_id in candidates:
            package = package_table.lookup(package_id)
            miles_away = distance_table.distance_between(current_address, package.address)
            deadline_seconds = (package.deadline.total_seconds()
                                if package.deadline is not None else NO_DEADLINE)
            key = (miles_away, deadline_seconds, package_id)
            if best_key is None or key < best_key:
                best_id, best_key = package_id, key

        next_address = package_table.lookup(best_id).address
        leg_miles = distance_table.distance_between(current_address, next_address)
        miles += leg_miles
        current_time = current_time + travel_time(leg_miles, speed_mph)
        current_address = next_address

        # Hand over every remaining package for this address (deliveries are instant).
        delivered_here = sorted(pid for pid in remaining
                                if package_table.lookup(pid).address == next_address)
        for package_id in delivered_here:
            remaining.remove(package_id)
            deadline = package_table.lookup(package_id).deadline
            if deadline is not None and current_time > deadline:
                late.append(package_id)
        stops.append(_PlannedStop(next_address, current_time, miles, delivered_here))

    return stops, miles, late


ROUTE_VARIANTS = [
    ("none", "nearest neighbor"),
    ("deadline", "deadline-first nearest neighbor"),
    ("earliest", "earliest-deadline-first nearest neighbor"),
]


def plan_route(truck, package_table, distance_table):
    """
    Step 3 of the algorithm: try every nearest-neighbor variant for this truck. Keep
    the shortest one that meets every deadline. If none does, keep the one with the
    fewest late packages so the problem appears clearly in the validation report.
    """
    best = None
    for priority, name in ROUTE_VARIANTS:
        stops, miles, late = _nearest_neighbor_route(
            truck.package_ids, package_table, distance_table,
            truck.departure_time, truck.speed_mph, priority)
        score = (len(late), miles)
        if best is None or score < best[0]:
            best = (score, stops, miles, name)
    return best[1], best[2], best[3]


def _commit_route(truck, stops, miles, strategy, package_table, distance_table):
    """Record the chosen route on the truck and stamp every package's delivery record."""
    truck.route_strategy = strategy
    truck.stops = [RouteStop(truck.departure_time, distance_table.hub_address,
                             distance_table.name_of(distance_table.hub_address), 0.0, [])]
    for package_id in truck.package_ids:
        package = package_table.lookup(package_id)
        package.truck_id = truck.truck_id
        package.departure_time = truck.departure_time
        package.status = STATUS_EN_ROUTE  # loaded and on the road
    for stop in stops:
        truck.stops.append(RouteStop(stop.arrival_time, stop.address,
                                     distance_table.name_of(stop.address),
                                     stop.miles_so_far, stop.package_ids))
        for package_id in stop.package_ids:
            package = package_table.lookup(package_id)
            package.delivery_time = stop.arrival_time
            package.status = STATUS_DELIVERED
    truck.total_miles = miles
    truck.finish_time = stops[-1].arrival_time if stops else truck.departure_time
    truck.end_time = truck.finish_time


def _miles_home(truck, distance_table):
    return distance_table.distance_between(truck.stops[-1].address, distance_table.hub_address)


def _send_truck_home(truck, distance_table):
    """Add the drive back to the hub, so its driver can take out another truck."""
    miles_home = _miles_home(truck, distance_table)
    truck.total_miles += miles_home
    truck.end_time = truck.finish_time + travel_time(miles_home, truck.speed_mph)
    truck.returns_to_hub = True
    truck.stops.append(RouteStop(truck.end_time, distance_table.hub_address,
                                 distance_table.name_of(distance_table.hub_address),
                                 truck.total_miles, []))


# -------------------------------------------------------------------------- dispatch
def dispatch_trucks(trucks, package_table, distance_table, number_of_drivers, day_start):
    """
    Step 2 of the algorithm: give each truck a driver and a departure time, then
    route it (step 3) as it leaves.

    Each driver is a small list: [driver_id, truck_currently_assigned]. A driver with
    no truck yet is at the hub from the start of the day.
    """
    # A truck is ready once every package on it can leave the hub (delays, address fixes).
    for truck in trucks:
        truck.ready_time = _ready_time(truck.package_ids, package_table, day_start)

    drivers = []
    for driver_number in range(1, number_of_drivers + 1):
        drivers.append([driver_number, None])

    # Most urgent deadline first, then the earliest ready time. Empty trucks stay home.
    dispatch_order = [truck for truck in trucks if truck.package_ids]
    dispatch_order.sort(key=lambda t: (_earliest_deadline(t.package_ids, package_table),
                                       t.ready_time, t.truck_id))

    for truck in dispatch_order:
        # Find the driver who can be at the hub soonest.
        best_driver, best_time = None, None
        for driver in drivers:
            current = driver[1]
            if current is None:
                free_at = day_start
            else:
                free_at = current.finish_time + travel_time(_miles_home(current, distance_table),
                                                            current.speed_mph)
            if best_time is None or free_at < best_time:
                best_driver, best_time = driver, free_at

        # If that driver is out on another truck, that truck now drives back to the hub.
        if best_driver[1] is not None:
            _send_truck_home(best_driver[1], distance_table)

        truck.driver_id = best_driver[0]
        truck.departure_time = max(truck.ready_time, best_time)

        # The corrected address is known by departure time (it is part of the ready
        # time), so the truck routes to the right place.
        for package_id in truck.package_ids:
            package = package_table.lookup(package_id)
            if (package.correction is not None
                    and package.correction.effective_time <= truck.departure_time):
                package.apply_address_correction()

        stops, miles, strategy = plan_route(truck, package_table, distance_table)
        _commit_route(truck, stops, miles, strategy, package_table, distance_table)
        best_driver[1] = truck


def run_delivery_day(package_table, distance_table, trucks, number_of_drivers, day_start):
    """Run the whole day: load the trucks, then dispatch and route them."""
    load_trucks(package_table, distance_table, trucks, day_start)
    dispatch_trucks(trucks, package_table, distance_table, number_of_drivers, day_start)
    return trucks
