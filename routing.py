"""
routing.py - Decides which truck carries each package, the order of the stops, and
when each truck leaves. This file holds the core algorithm.

THE ALGORITHM, IN THREE STEPS
-----------------------------
1. LOAD THE TRUCKS (constraint-aware greedy loading)
   a. Packages that "must be delivered with" each other are joined into one bundle
      (a union-find over package IDs). A bundle always rides on one truck.
   b. Bundles are placed by rules, most constrained first:
        - a required truck ("Can only be on truck 2")      -> that truck
        - delayed packages ("will not arrive until 9:05")  -> the LATE truck, which
                                                              waits at the hub for them
        - a wrong address, fixed later in the day           -> the SECOND-WAVE truck,
                                                              which leaves after the fix
        - any other delivery deadline                       -> the EARLY truck (leaves
                                                              at 8:00 AM)
        - end-of-day (EOD) packages                         -> see (c)
   c. EOD bundles are placed by a self-adjusting "nearest cluster" rule. Each round
      picks the unplaced bundle that is closest (in miles) to any address already on
      a truck with room, and puts it on that truck. Packages for the same address,
      or for a nearby one, end up on the same truck, which keeps the routes short.

2. ORDER THE STOPS (nearest-neighbor heuristic, with a deadline-first variant)
   Starting at the hub, the truck always drives to the closest address it still has
   packages for, and drops off every package for that address at once. This is a
   greedy, self-adjusting heuristic: each choice depends on where the truck is now.
   Two variants are tried for every truck:
        - plain nearest neighbor
        - deadline-first nearest neighbor (stops with a deadline package come first)
   The shorter variant that delivers every package on time is kept.

3. DISPATCH THE TRUCKS (only as many trucks on the road as there are drivers)
   Trucks leave in order of their ready time (the latest time any of their packages
   can leave the hub). When no driver is free, the truck waits for the driver who can
   get back to the hub soonest. Only that driver's truck drives back to the hub;
   the other trucks end the day at their last stop.

COMPLEXITY (n packages, L locations, T trucks, B bundles)
   Bundling O(n * a(n)) | Loading O(B^2 * n) | Routing O(n * L) per truck |
   Dispatch O(T^2)   -> overall O(n^3) in the worst case, which is instant for 40 packages.
"""

from package import STATUS_DELIVERED
from time_utils import travel_time
from truck import RouteStop


# --------------------------------------------------------------------------- bundles
def build_bundles(package_table):
    """
    Join packages that must travel together into bundles, using union-find.

    "Must be delivered with" is transitive: if 14 goes with 15 and 19, and 16 goes with
    13 and 19, then 13, 14, 15, 16, 19 and 20 must all share one truck. Union-find
    merges these groups efficiently. The parent links are kept in a plain list indexed
    by package ID (no dictionary).
    """
    package_ids = package_table.keys()
    largest_id = package_ids[-1] if package_ids else 0
    parent = list(range(largest_id + 1))

    def find(package_id):
        # Follow parent links to the group's root, flattening the path as we go.
        while parent[package_id] != package_id:
            parent[package_id] = parent[parent[package_id]]
            package_id = parent[package_id]
        return package_id

    def union(first_id, second_id):
        root_a, root_b = find(first_id), find(second_id)
        if root_a != root_b:
            parent[root_b] = root_a

    for package_id in package_ids:
        for partner_id in package_table.lookup(package_id).bundle_ids:
            if partner_id in package_table:
                union(package_id, partner_id)

    # Collect the members of each group (list of lists, ordered by root ID).
    members_by_root = []
    for _ in range(largest_id + 1):
        members_by_root.append([])
    for package_id in package_ids:
        members_by_root[find(package_id)].append(package_id)
    return [members for members in members_by_root if members]


# --------------------------------------------------------------------------- loading
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


def _first_truck_with_room(preferred_trucks, bundle):
    for truck in preferred_trucks:
        if truck.has_room_for(len(bundle)):
            return truck
    raise ValueError(f"No truck has room for bundle {bundle}.")


def _distance_to_truck(bundle, truck, package_table, distance_table):
    """
    How close a bundle is to the packages already on a truck: the shortest distance
    from any bundle address to any address on the truck. An empty truck is measured
    from the hub.
    """
    best = None
    for package_id in bundle:
        bundle_address = package_table.lookup(package_id).address
        if not truck.package_ids:
            miles = distance_table.distance_between(distance_table.hub_address, bundle_address)
            best = miles if best is None or miles < best else best
            continue
        for loaded_id in truck.package_ids:
            loaded_address = package_table.lookup(loaded_id).address
            miles = distance_table.distance_between(loaded_address, bundle_address)
            if best is None or miles < best:
                best = miles
    return best


def load_trucks(package_table, distance_table, trucks):
    """
    Step 1 of the algorithm: assign every package to a truck (see the module docstring).

    trucks[0] is the EARLY truck, trucks[1] the LATE truck (waits for delayed packages),
    and trucks[-1] the SECOND-WAVE truck (leaves when a driver returns, after any
    address corrections are known).
    """
    early_truck = trucks[0]
    late_truck = trucks[1] if len(trucks) > 1 else trucks[0]
    second_wave_truck = trucks[-1]

    def truck_number(number):
        for truck in trucks:
            if truck.truck_id == number:
                return truck
        raise ValueError(f"A package requires truck {number}, but there is no such truck.")

    end_of_day_bundles = []
    deadline_bundles = []

    for bundle in build_bundles(package_table):
        required = _bundle_required_truck(bundle, package_table)
        if required is not None:
            target = truck_number(required)
            if not target.has_room_for(len(bundle)):
                raise ValueError(f"Truck {required} is too full for required bundle {bundle}.")
            target.load(bundle)
        elif _bundle_has(bundle, package_table, lambda p: p.hub_arrival_time is not None):
            _first_truck_with_room([late_truck, second_wave_truck], bundle).load(bundle)
        elif _bundle_has(bundle, package_table, lambda p: p.correction is not None):
            _first_truck_with_room([second_wave_truck], bundle).load(bundle)
        elif _bundle_has(bundle, package_table, lambda p: p.deadline is not None):
            deadline_bundles.append(bundle)
        else:
            end_of_day_bundles.append(bundle)

    # Deadline packages go out first. Larger bundles are placed first so they still fit.
    deadline_bundles.sort(key=lambda b: (-len(b), b[0]))
    for bundle in deadline_bundles:
        _first_truck_with_room([early_truck, late_truck, second_wave_truck], bundle).load(bundle)

    # EOD packages: repeatedly place the bundle that is closest to any truck with room.
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
            raise ValueError("The trucks are full. There are more packages than total capacity.")
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
                            speed_mph, deadline_first):
    """
    Build one candidate route with the nearest-neighbor heuristic.

    From the current location, pick the closest address that still has packages
    waiting. With deadline_first=True, only addresses that hold a deadline package are
    considered until none are left. Every package for the chosen address is delivered
    in a single stop.

    Returns (stops, total_miles, late_package_ids). Nothing on the packages is changed.
    """
    remaining = list(package_ids)
    current_address = distance_table.hub_address
    current_time = departure_time
    miles = 0.0
    stops = []
    late = []

    while remaining:
        # Which packages are we allowed to choose from right now?
        candidates = remaining
        if deadline_first:
            with_deadline = [pid for pid in remaining
                             if package_table.lookup(pid).deadline is not None]
            if with_deadline:
                candidates = with_deadline

        # Greedy choice: the closest candidate address. Ties go to the earlier deadline,
        # then the lower package ID, so the result is always the same.
        best_id, best_key = None, None
        for package_id in candidates:
            package = package_table.lookup(package_id)
            miles_away = distance_table.distance_between(current_address, package.address)
            deadline_seconds = (package.deadline.total_seconds()
                                if package.deadline is not None else float("inf"))
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


def plan_route(truck, package_table, distance_table):
    """
    Step 2 of the algorithm: try both nearest-neighbor variants for this truck. Keep
    the shortest one that meets every deadline. If neither does, keep the one with the
    fewest late packages so the problem appears clearly in the validation report.
    """
    candidates = []
    for deadline_first in (False, True):
        stops, miles, late = _nearest_neighbor_route(
            truck.package_ids, package_table, distance_table,
            truck.departure_time, truck.speed_mph, deadline_first)
        name = "deadline-first nearest neighbor" if deadline_first else "nearest neighbor"
        candidates.append((len(late), miles, name, stops))

    candidates.sort(key=lambda c: (c[0], c[1]))
    _, miles, name, stops = candidates[0]
    return stops, miles, name


def _commit_route(truck, stops, miles, strategy, package_table, distance_table):
    """Record the chosen route on the truck and stamp every package's delivery record."""
    truck.route_strategy = strategy
    truck.stops = [RouteStop(truck.departure_time, distance_table.hub_address,
                             distance_table.name_of(distance_table.hub_address), 0.0, [])]
    for stop in stops:
        truck.stops.append(RouteStop(stop.arrival_time, stop.address,
                                     distance_table.name_of(stop.address),
                                     stop.miles_so_far, stop.package_ids))
        for package_id in stop.package_ids:
            package = package_table.lookup(package_id)
            package.truck_id = truck.truck_id
            package.departure_time = truck.departure_time
            package.delivery_time = stop.arrival_time
            package.status = STATUS_DELIVERED
    truck.total_miles = miles
    truck.finish_time = stops[-1].arrival_time if stops else truck.departure_time
    truck.end_time = truck.finish_time


def _send_truck_home(truck, distance_table):
    """Add the drive back to the hub, so its driver can take out another truck."""
    last_address = truck.stops[-1].address
    miles_home = distance_table.distance_between(last_address, distance_table.hub_address)
    truck.total_miles += miles_home
    truck.end_time = truck.finish_time + travel_time(miles_home, truck.speed_mph)
    truck.returns_to_hub = True
    truck.stops.append(RouteStop(truck.end_time, distance_table.hub_address,
                                 distance_table.name_of(distance_table.hub_address),
                                 truck.total_miles, []))


# -------------------------------------------------------------------------- dispatch
def dispatch_trucks(trucks, package_table, distance_table, number_of_drivers, day_start):
    """
    Step 3 of the algorithm: give each truck a driver and a departure time, then route it.

    Each driver is a small list: [driver_id, time_free_at_hub, truck_currently_driving].
    """
    # Before routing, apply any address correction whose time has come by the time the
    # truck can leave. Each truck's ready time already includes those correction times.
    for truck in trucks:
        truck.ready_time = day_start
        for package_id in truck.package_ids:
            package = package_table.lookup(package_id)
            ready = package.earliest_ready_time(day_start)
            if ready > truck.ready_time:
                truck.ready_time = ready

    drivers = []
    for driver_number in range(1, number_of_drivers + 1):
        drivers.append([driver_number, day_start, None])

    dispatch_order = [truck for truck in trucks if truck.package_ids]
    dispatch_order.sort(key=lambda t: (t.ready_time, t.truck_id))

    for truck in dispatch_order:
        # Find the driver who can be at the hub soonest.
        best_driver, best_time = None, None
        for driver in drivers:
            if driver[2] is None:
                free_at = driver[1]
            else:
                current = driver[2]
                last_address = current.stops[-1].address
                miles_home = distance_table.distance_between(last_address,
                                                             distance_table.hub_address)
                free_at = current.finish_time + travel_time(miles_home, current.speed_mph)
            if best_time is None or free_at < best_time:
                best_driver, best_time = driver, free_at

        # If that driver is out on another truck, that truck now drives back to the hub.
        if best_driver[2] is not None:
            _send_truck_home(best_driver[2], distance_table)

        truck.driver_id = best_driver[0]
        truck.departure_time = max(truck.ready_time, best_time)

        # The address correction is known by departure time, so apply it now.
        for package_id in truck.package_ids:
            package = package_table.lookup(package_id)
            if package.correction is not None and package.correction.effective_time <= truck.departure_time:
                package.apply_address_correction()

        stops, miles, strategy = plan_route(truck, package_table, distance_table)
        _commit_route(truck, stops, miles, strategy, package_table, distance_table)
        best_driver[1] = truck.end_time
        best_driver[2] = truck


def run_delivery_day(package_table, distance_table, trucks, number_of_drivers, day_start):
    """Run the whole day: load the trucks, dispatch them, and route every delivery."""
    load_trucks(package_table, distance_table, trucks)
    dispatch_trucks(trucks, package_table, distance_table, number_of_drivers, day_start)
    return trucks
