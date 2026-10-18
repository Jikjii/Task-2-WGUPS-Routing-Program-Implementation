"""
truck.py - The Truck class: what a truck carries, where it goes, and when.

A truck records each stop it makes (time, address, miles driven so far). The
supervisor interface can then ask "how far had this truck driven at 10:00 AM?"
without re-running the simulation.
"""

from time_utils import format_time


class RouteStop:
    """One stop on a truck's route."""

    def __init__(self, arrival_time, address, location_name, miles_so_far, package_ids):
        self.arrival_time = arrival_time
        self.address = address
        self.location_name = location_name
        self.miles_so_far = miles_so_far
        self.package_ids = package_ids  # packages handed over at this stop (empty for the hub)


class Truck:
    """A delivery truck with a fixed capacity, travelling at a constant average speed."""

    def __init__(self, truck_id, capacity, speed_mph):
        self.truck_id = truck_id
        self.capacity = capacity
        self.speed_mph = speed_mph

        self.package_ids = []        # every package loaded onto this truck at the hub
        self.ready_time = None       # earliest time every loaded package can leave the hub
        self.driver_id = None
        self.departure_time = None
        self.stops = []              # RouteStop list, in the order they were visited
        self.finish_time = None      # time of the last delivery
        self.returns_to_hub = False  # True if a driver must bring it back for another truck
        self.end_time = None         # finish_time, or the hub arrival time if it returns
        self.total_miles = 0.0
        self.route_strategy = ""     # which routing variant produced the chosen route

    def has_room_for(self, count):
        return len(self.package_ids) + count <= self.capacity

    def load(self, package_ids):
        """Put packages on the truck. The caller checks has_room_for first."""
        for package_id in package_ids:
            self.package_ids.append(package_id)

    def miles_at(self, query_time):
        """
        Miles this truck has driven by `query_time`. Trucks never pause between stops
        (deliveries are instantaneous), so mileage grows at exactly speed_mph while
        the truck is out.
        """
        if self.departure_time is None or query_time <= self.departure_time:
            return 0.0
        if query_time >= self.end_time:
            return self.total_miles
        hours_driving = (query_time - self.departure_time).total_seconds() / 3600
        return min(self.total_miles, hours_driving * self.speed_mph)

    def status_at(self, query_time):
        """A one-line description of the truck at `query_time`."""
        if self.departure_time is None or query_time < self.departure_time:
            return f"At the hub (scheduled to leave {format_time(self.departure_time)})"
        if query_time >= self.end_time:
            if self.returns_to_hub:
                return f"Finished route and back at the hub at {format_time(self.end_time)}"
            return f"Finished all deliveries at {format_time(self.end_time)}"
        return f"Out for delivery (left hub {format_time(self.departure_time)})"
