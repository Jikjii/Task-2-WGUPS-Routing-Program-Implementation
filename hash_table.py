"""
hash_table.py - A self-adjusting hash table written from scratch (requirements A and B).

WHY A CUSTOM HASH TABLE?
    The program has to look packages up by ID many times: while loading the trucks,
    while simulating every delivery, and every time the supervisor asks for a status.
    A hash table gives average O(1) insert and look-up, no matter how many packages
    a city has. The task does not allow Python's built-in dictionary, so this file
    builds the table using only plain Python lists.

HOW IT WORKS (separate chaining):
    * The table is a list of "buckets". Each bucket is a list of [key, value] pairs.
    * hash(key) % number_of_buckets chooses the bucket that a key belongs in.
    * If two keys land in the same bucket (a "collision"), they simply sit side by
      side inside that bucket's list, so nothing is ever overwritten by accident.

SELF-ADJUSTING BEHAVIOR:
    The table keeps track of its load factor (items / buckets). When the load factor
    rises above MAX_LOAD_FACTOR, the table doubles its bucket count and re-hashes every
    item. Buckets therefore stay short, and look-ups stay O(1) on average even if a
    larger city has thousands of packages instead of 40.
"""


class ChainingHashTable:
    """A hash table that uses separate chaining (a list of lists) to store key/value pairs."""

    # Grow the table once there is, on average, more than one item per bucket.
    MAX_LOAD_FACTOR = 1.0

    def __init__(self, initial_capacity=10):
        # Build the empty buckets. Each bucket is its own (initially empty) list.
        # Space complexity: O(n) for n stored items plus O(b) for b buckets.
        if initial_capacity < 1:
            initial_capacity = 1
        self.buckets = []
        for _ in range(initial_capacity):
            self.buckets.append([])
        self.item_count = 0

    # ------------------------------------------------------------------ helpers
    def _bucket_index(self, key):
        """Turn any hashable key into a bucket number. O(1)."""
        return hash(key) % len(self.buckets)

    def _resize(self, new_capacity):
        """Re-hash every stored item into a larger list of buckets. O(n), but rare."""
        old_buckets = self.buckets
        self.buckets = []
        for _ in range(new_capacity):
            self.buckets.append([])
        for bucket in old_buckets:
            for key, value in bucket:
                self.buckets[self._bucket_index(key)].append([key, value])

    # ---------------------------------------------------------------- public API
    def insert(self, key, value):
        """
        Insert a key/value pair, or update the value if the key already exists.

        For WGUPS the key is the package ID and the value is the Package object. That
        object holds the delivery address, deadline, city, zip code, weight, and
        delivery status (with delivery time) for the package.

        Average time complexity: O(1). Worst case O(n) if every key collides.
        """
        bucket = self.buckets[self._bucket_index(key)]

        # If the key is already present, update it in place (no duplicates allowed).
        for pair in bucket:
            if pair[0] == key:
                pair[1] = value
                return

        # Otherwise append a new [key, value] pair to the end of the bucket's chain.
        bucket.append([key, value])
        self.item_count += 1

        # Self-adjust: if the chains are getting long, double the number of buckets.
        if self.item_count / len(self.buckets) > self.MAX_LOAD_FACTOR:
            self._resize(len(self.buckets) * 2)

    def lookup(self, key):
        """
        Return the value stored for `key`, or None if the key is not in the table.

        Average time complexity: O(1). Only the one bucket the key hashes to is searched.
        """
        bucket = self.buckets[self._bucket_index(key)]
        for pair in bucket:
            if pair[0] == key:
                return pair[1]
        return None

    def remove(self, key):
        """Remove `key` from the table. Return True if it was found and removed. O(1) average."""
        bucket = self.buckets[self._bucket_index(key)]
        for position in range(len(bucket)):
            if bucket[position][0] == key:
                bucket.pop(position)
                self.item_count -= 1
                return True
        return False

    def keys(self):
        """Return every key in the table as a sorted list. O(n log n) because of the sort."""
        all_keys = []
        for bucket in self.buckets:
            for pair in bucket:
                all_keys.append(pair[0])
        all_keys.sort()
        return all_keys

    def values(self):
        """Return every stored value, ordered by key. O(n log n)."""
        result = []
        for key in self.keys():
            result.append(self.lookup(key))
        return result

    def __len__(self):
        return self.item_count

    def __contains__(self, key):
        for pair in self.buckets[self._bucket_index(key)]:
            if pair[0] == key:
                return True
        return False
