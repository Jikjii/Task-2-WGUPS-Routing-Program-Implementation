"""
package.py - The Package class: one parcel and everything WGUPS knows about it.

A Package object is the "value" stored in the hash table (the key is its package ID).
It carries every data component the task asks for:
    delivery address, delivery deadline, delivery city, delivery zip code,
    package weight, and delivery status (delayed / at the hub / en route / delivered)
    including the delivery time.

It also carries the delivery CONSTRAINTS read from the "Special Notes" column, so the
routing code can make decisions without re-reading the raw text.
"""

import re

from time_utils import format_time, parse_time

# Status values a package moves through during the day.
STATUS_DELAYED = "Delayed"
STATUS_AT_HUB = "At the hub"
STATUS_EN_ROUTE = "En route"
STATUS_DELIVERED = "Delivered"


class AddressCorrection:
    """A known future fix to a package's address (for example package 9 at 10:20 AM)."""

    def __init__(self, package_id, effective_time, address, city, state, zip_code):
        self.package_id = package_id
        self.effective_time = effective_time  # WGUPS does not know the new address before this
        self.address = address
        self.city = city
        self.state = state
        self.zip_code = zip_code


class Package:
    """One package, its delivery constraints, and (after the simulation) its delivery record."""

    def __init__(self, package_id, address, city, state, zip_code, deadline_text, weight, notes):
        # ---- Data components from the WGUPS Package File ----
        self.package_id = package_id
        self.address = address
        self.city = city
        self.state = state
        self.zip_code = zip_code
        self.deadline_text = deadline_text  # "EOD" or e.g. "10:30 AM", kept for display
        self.deadline = None if deadline_text.upper() == "EOD" else parse_time(deadline_text)
        self.weight = weight
        self.notes = notes

        # ---- Constraints derived from the special note (filled in by apply_special_note) ----
        self.required_truck = None      # e.g. "Can only be on truck 2" -> 2
        self.hub_arrival_time = None    # e.g. "Delayed on flight ... until 9:05 am" -> 9:05
        self.bundle_ids = []            # e.g. "Must be delivered with 15, 19" -> [15, 19]
        self.has_wrong_address = False  # "Wrong address listed"
        self.correction = None          # AddressCorrection once WGUPS supplies the fix

        # Keep the address as originally listed so the status report can show what the
        # supervisor would have seen before the address was corrected.
        self.listed_address = address
        self.listed_city = city
        self.listed_state = state
        self.listed_zip_code = zip_code

        # ---- Delivery record (filled in by the delivery simulation) ----
        self.status = STATUS_AT_HUB
        self.truck_id = None
        self.departure_time = None
        self.delivery_time = None

        self.apply_special_note()

    # ------------------------------------------------------------------ constraints
    def apply_special_note(self):
        """
        Translate the free-text "Special Notes" column into structured constraints.

        The patterns are generic: a package file from another city that uses the same
        wording (truck numbers, delay times, bundles) works without code changes.
        """
        note = self.notes.lower()
        if not note:
            return

        truck_match = re.search(r"can only be on truck\s*(\d+)", note)
        if truck_match:
            self.required_truck = int(truck_match.group(1))

        delay_match = re.search(r"until\s*(\d{1,2}:\d{2}\s*[ap]\.?m\.?)", note)
        if "delayed" in note and delay_match:
            self.hub_arrival_time = parse_time(delay_match.group(1))
            self.status = STATUS_DELAYED

        bundle_match = re.search(r"must be delivered with\s*(.*)", note)
        if bundle_match:
            self.bundle_ids = [int(number) for number in re.findall(r"\d+", bundle_match.group(1))]

        if "wrong address" in note:
            self.has_wrong_address = True

    def set_address_correction(self, correction):
        """Attach the corrected address. It only takes effect at correction.effective_time."""
        self.correction = correction

    def apply_address_correction(self):
        """Swap in the corrected address (called once the correction time has passed)."""
        if self.correction is not None:
            self.address = self.correction.address
            self.city = self.correction.city
            self.state = self.correction.state
            self.zip_code = self.correction.zip_code
            self.has_wrong_address = False

    def earliest_ready_time(self, day_start):
        """The earliest time this package can leave the hub on a truck."""
        ready = day_start
        if self.hub_arrival_time is not None and self.hub_arrival_time > ready:
            ready = self.hub_arrival_time
        if self.correction is not None and self.correction.effective_time > ready:
            ready = self.correction.effective_time
        return ready

    # ------------------------------------------------------------- time-based views
    def address_at(self, query_time):
        """
        Return (address, city, state, zip) as WGUPS knew it at `query_time`.
        Before a correction takes effect, this is the (wrong) listed address.
        """
        if self.correction is not None and query_time < self.correction.effective_time:
            return self.listed_address, self.listed_city, self.listed_state, self.listed_zip_code
        if self.correction is not None:
            return (self.correction.address, self.correction.city,
                    self.correction.state, self.correction.zip_code)
        return self.address, self.city, self.state, self.zip_code

    def status_at(self, query_time):
        """
        Return (status, status_text) for this package at `query_time`.

        status is one of: Delayed, At the hub, En route, Delivered.
        status_text adds the time, e.g. "Delivered at 09:24 AM".
        """
        if self.delivery_time is not None and query_time >= self.delivery_time:
            return STATUS_DELIVERED, f"Delivered at {format_time(self.delivery_time)}"
        if self.departure_time is not None and query_time >= self.departure_time:
            return STATUS_EN_ROUTE, (f"En route on truck {self.truck_id} "
                                     f"(left hub {format_time(self.departure_time)})")
        if self.hub_arrival_time is not None and query_time < self.hub_arrival_time:
            return STATUS_DELAYED, (f"Delayed on flight - arrives at hub "
                                    f"{format_time(self.hub_arrival_time)}")
        return STATUS_AT_HUB, "At the hub"

    def __str__(self):
        return (f"Package {self.package_id}: {self.address}, {self.city}, {self.state} "
                f"{self.zip_code} | deadline {self.deadline_text} | {self.weight} kg | {self.status}")
