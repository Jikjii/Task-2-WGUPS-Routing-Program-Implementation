"""
validation.py - Re-checks the finished delivery plan against the WGUPS scenario rules.

The routing code is designed to obey the rules. This file then confirms the
recorded result (truck loads, departure times, delivery times, drivers, mileage), so
the supervisor and a grader can see which requirements were met and the evidence for
each. validate_day returns one CheckResult per rule. main.py prints them as
[PASS] or [FAIL] lines.
"""

from time_utils import format_time


class CheckResult:
    """The outcome of one rule check: passed or not, the rule, and the evidence."""

    def __init__(self, passed, rule, detail):
        self.passed = passed
        self.rule = rule
        self.detail = detail

    def __str__(self):
        return f"[{'PASS' if self.passed else 'FAIL'}] {self.rule}: {self.detail}"


def _truck_list(truck_ids):
    """Format truck numbers as 'truck 1' or 'trucks 1, 2'."""
    if len(truck_ids) == 1:
        return f"truck {truck_ids[0]}"
    return "trucks " + ", ".join(str(t) for t in truck_ids)


def validate_day(package_table, trucks, number_of_drivers, day_start, mileage_limit):
    """Run every check and return a list of CheckResult objects."""
    packages = package_table.values()
    results = []

    # 1. Every package was delivered.
    undelivered = [p.package_id for p in packages if p.delivery_time is None]
    results.append(CheckResult(
        not undelivered, "All packages delivered",
        f"{len(packages) - len(undelivered)} of {len(packages)} delivered"
        + (f"; missing {undelivered}" if undelivered else "")))

    # 2. Every deadline was met (and report the smallest margin, the "closest call").
    late = [f"#{p.package_id} at {format_time(p.delivery_time)} (due {p.deadline_text})"
            for p in packages
            if p.deadline is not None and p.delivery_time is not None
            and p.delivery_time > p.deadline]
    with_deadline = [p for p in packages if p.deadline is not None]
    smallest_margin = None
    for p in with_deadline:
        if p.delivery_time is not None:
            margin = p.deadline - p.delivery_time
            if smallest_margin is None or margin < smallest_margin:
                smallest_margin = margin
    detail = f"{len(with_deadline)} deadline packages on time"
    if smallest_margin is not None and not late:
        detail += f" (closest call: {int(smallest_margin.total_seconds() // 60)} min to spare)"
    results.append(CheckResult(not late, "Delivery deadlines met",
                               detail if not late else "; ".join(late)))

    # 3. No truck carried more than its capacity.
    over = [f"truck {t.truck_id} has {len(t.package_ids)}" for t in trucks
            if len(t.package_ids) > t.capacity]
    loads = ", ".join(f"T{t.truck_id}={len(t.package_ids)}" for t in trucks)
    results.append(CheckResult(not over, f"Truck capacity ({trucks[0].capacity} max)",
                               loads if not over else "; ".join(over)))

    # 4. Truck-restricted packages rode on the right truck.
    restricted = [p for p in packages if p.required_truck is not None]
    wrong_truck = [f"#{p.package_id} on truck {p.truck_id}" for p in restricted
                   if p.truck_id != p.required_truck]
    results.append(CheckResult(
        not wrong_truck, "Truck restrictions",
        (f"packages {[p.package_id for p in restricted]} all on their required truck"
         if not wrong_truck else "; ".join(wrong_truck))))

    # 5. Delayed packages did not leave the hub before they arrived there.
    delayed = [p for p in packages if p.hub_arrival_time is not None]
    too_early = [f"#{p.package_id} left before {format_time(p.hub_arrival_time)}" for p in delayed
                 if p.departure_time is None or p.departure_time < p.hub_arrival_time]
    results.append(CheckResult(
        not too_early, "Delayed packages leave after arriving at the hub",
        (f"packages {[p.package_id for p in delayed]} left at or after their arrival"
         if not too_early else "; ".join(too_early))))

    # 6. Packages that must be delivered together shared a truck.
    split = []
    group_members = []
    for p in packages:
        for partner_id in p.bundle_ids:
            partner = package_table.lookup(partner_id)
            if partner is None:
                continue
            for member in (p.package_id, partner_id):
                if member not in group_members:
                    group_members.append(member)
            if partner.truck_id != p.truck_id:
                split.append(f"#{p.package_id} (truck {p.truck_id}) vs "
                             f"#{partner_id} (truck {partner.truck_id})")
    group_members.sort()
    group_trucks = sorted(set(package_table.lookup(pid).truck_id for pid in group_members))
    results.append(CheckResult(
        not split, "Packages that must be delivered together",
        (f"packages {group_members} on {_truck_list(group_trucks)}" if group_members
         else "none in this package file") if not split else "; ".join(split)))

    # 7. Wrong-address packages: the fix must be known before the truck leaves, and the
    #    package must go to the corrected address. A "Wrong address listed" note with
    #    no correction supplied is a failure too.
    flagged = [p for p in packages if p.correction is not None or p.has_wrong_address]
    bad = []
    for p in flagged:
        if p.correction is None:
            bad.append(f"#{p.package_id} has no corrected address in the settings")
        elif p.departure_time is None or p.departure_time < p.correction.effective_time:
            bad.append(f"#{p.package_id} left the hub before the fix was known")
        elif p.address != p.correction.address:
            bad.append(f"#{p.package_id} delivered to {p.address}")
    if bad:
        detail = "; ".join(bad)
    elif flagged:
        detail = "; ".join(f"#{p.package_id} left hub {format_time(p.departure_time)} (fix known "
                           f"{format_time(p.correction.effective_time)}); delivered to "
                           f"{p.address} at {format_time(p.delivery_time)}" for p in flagged)
    else:
        detail = "none in this package file"
    results.append(CheckResult(not bad, "Wrong address corrected", detail))

    # 8. No truck left before the start of the day.
    early = [f"truck {t.truck_id} left {format_time(t.departure_time)}" for t in trucks
             if t.departure_time is not None and t.departure_time < day_start]
    departures = ", ".join(f"T{t.truck_id} {format_time(t.departure_time)}"
                           for t in trucks if t.departure_time is not None)
    results.append(CheckResult(not early, f"Trucks leave no earlier than {format_time(day_start)}",
                               departures if not early else "; ".join(early)))

    # 9. Drivers: never more trucks on the road than drivers, and a driver who takes a
    #    second truck must first have brought the earlier truck back to the hub.
    used = [t for t in trucks if t.departure_time is not None]
    max_on_road = 0
    for t in used:
        on_road = sum(1 for other in used
                      if other.departure_time <= t.departure_time < other.end_time)
        max_on_road = max(max_on_road, on_road)
    driver_problems = []
    for driver_id in sorted(set(t.driver_id for t in used)):
        driven = sorted((t for t in used if t.driver_id == driver_id),
                        key=lambda t: t.departure_time)
        for earlier, later in zip(driven, driven[1:]):
            if not earlier.returns_to_hub or earlier.end_time > later.departure_time:
                driver_problems.append(f"driver {driver_id} was not back at the hub from "
                                       f"truck {earlier.truck_id} when truck {later.truck_id} left")
    passed = max_on_road <= number_of_drivers and not driver_problems
    if driver_problems:
        detail = "; ".join(driver_problems)
    else:
        detail = (f"at most {max_on_road} trucks on the road at once; "
                  + ", ".join(f"T{t.truck_id}=driver {t.driver_id}" for t in used))
    results.append(CheckResult(passed, f"Drivers ({number_of_drivers} available)", detail))

    # 10. Combined mileage is under the limit.
    total = sum(t.total_miles for t in trucks)
    results.append(CheckResult(total < mileage_limit, f"Total mileage under {mileage_limit:g} miles",
                               f"{total:.1f} miles"))

    return results
