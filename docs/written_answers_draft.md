# WGUPS Routing Program: Written Answers (DRAFT)

> **This is a starting draft, not submission text.** WGU runs every submission through a
> similarity checker and expects original work. Rewrite each section in your own words, check
> every claim against your own run of the program, and keep only the sources you actually used.
> Every number below comes from `python main.py --summary` on the provided data.

---

## F1. Strengths of the algorithm

The solution uses a **constraint-aware greedy algorithm**. Packages are loaded onto trucks by rules
(most-constrained first, then a "nearest cluster" rule for end-of-day packages). Each truck's stops
are then ordered with the **nearest-neighbor heuristic**, trying three variants (plain,
deadline-first, earliest-deadline-first) and keeping the shortest route that meets every deadline.

**Strength 1: it is fast and scales well.** Nearest neighbor chooses each stop with one pass over the
packages still on the truck, so ordering one truck's route is O(k²) for k packages. The whole day
(loading, dispatch, routing and validation) runs in under 0.01 seconds for 40 packages. It stays
practical for a city with hundreds of packages, where checking every possible route (k! orders) is
impossible.

**Strength 2: it adjusts itself at every step.** Each choice depends on where the truck is right now
and which packages are still on board. No fixed route is written into the code. If a package is
added, an address changes, or a delay moves a departure time, the same code builds a new valid
route. Trying three variants for each truck and keeping the best on-time one lets the algorithm
trade distance against urgency automatically. On this data plain nearest neighbor won for all three
trucks because it met every deadline with the fewest miles.

**Strength 3: the constraints are data-driven and checked.** The special notes are parsed into
structured constraints: required truck, hub arrival time, bundle partners, wrong address. Loading
and routing use those constraints, not hard-coded package lists. After the day is planned, an
independent validation step re-checks every rule and prints `[PASS]`/`[FAIL]`. This supports the
stated goal of reusing the program for other cities.

## F2. Verification that the algorithm meets all requirements

| Requirement | How the solution meets it | Evidence (program output) |
|---|---|---|
| Deliver all 40 packages | Every package is loaded and routed | `[PASS] All packages delivered: 40 of 40` |
| Combined mileage under 140 miles | Nearest-neighbor routes, nearest-cluster loading | Truck 1: 34.0, Truck 2: 31.7, Truck 3: 27.8, **total 93.5 miles** |
| Every deadline met | Deadline packages go on the 8:00 truck. Routes that would be late are rejected | 14 deadline packages on time. Package 15 (9:00 AM) delivered 8:13 AM. Closest call: package 25 (10:30 AM) delivered 10:17 AM |
| Max 16 packages per truck | Loader checks capacity before every placement | T1=16, T2=16, T3=8 |
| Packages 3, 18, 36, 38 only on truck 2 | Required-truck bundles are loaded first | `[PASS] Truck restrictions` |
| Packages 6, 25, 28, 32 not at the hub until 9:05 | They ride truck 2, which waits for them; the truck's ready time is 9:05 | Truck 2 leaves 9:05 AM |
| 13, 14, 15, 16, 19, 20 delivered together | Union-find joins them into one bundle that rides one truck | All six on truck 1 |
| Package 9's address is unknown until 10:20 | Its truck's ready time is 10:20. The corrected address (410 S State St, 84111) is applied only at departure | Truck 3 leaves 10:20 AM, delivers package 9 at 11:12 AM to 410 S State St |
| Trucks leave no earlier than 8:00 AM | Dispatch starts at the 8:00 day start | Departures 8:00, 9:05, 10:20 |
| Two drivers for three trucks | At most two trucks are out at once. Truck 1 returns to the hub (9:54 AM) so driver 1 can take truck 3 | `[PASS] Drivers (2 available)` |
| Supervisor can see status at any time | Each package stores departure and delivery times. Status at any time is replayed from them | Interface options 1 and 2, screenshots D1-D3 |

## F3. Two other algorithms that would meet all requirements

1. **2-opt local search** (Croes, 1958)
2. **Simulated annealing** (Kirkpatrick, Gelatt, & Vecchi, 1983)

Both would reuse the same truck loading and dispatch rules. Only the route-ordering step would
change, so all the scenario constraints (truck restrictions, delays, bundles, package 9) are met the
same way. Each would also keep the deadline check and reject any route that delivers late.

### F3a. How each differs from the algorithm used

**2-opt** starts from a complete route, for example the nearest-neighbor route. It then repeatedly
picks two edges, reverses the section of the route between them, and keeps the change if the route
gets shorter (and stays on time). It stops when no swap helps.

| | Nearest neighbor (used) | 2-opt |
|---|---|---|
| How it builds a route | Constructive: grows the route one stop at a time and never revisits a choice | Improvement: rewrites a whole existing route |
| Looks at | Only the next stop | Pairs of edges across the whole route |
| Can it undo a bad early choice? | No | Yes: crossings and long back-tracks get removed |
| Cost | O(k²) for one route | O(k²) per pass, repeated until no improvement |

**Simulated annealing** also improves a complete route with small random changes, such as swapping
two stops or reversing a section. Unlike 2-opt, it sometimes **accepts a worse route on purpose**.
How likely that is depends on a "temperature" that starts high and slowly cools.

| | Nearest neighbor (used) | Simulated annealing |
|---|---|---|
| Deterministic? | Yes: same input, same route | No: random moves, so results can differ run to run unless the random seed is fixed |
| Escapes local minima? | No | Yes: accepting worse moves early lets it leave a poor region |
| Tuning needed | None | Starting temperature, cooling rate and number of iterations |
| Running time | Very short and predictable | Much longer; quality depends on how long it runs |

## G. What I would do differently

(Other than using 2-opt or simulated annealing.)

1. **Allow more than one trip per truck.** Each truck currently makes one trip, so the program can
   handle at most trucks × 16 packages (48 here). I would let a truck that returns to the hub reload
   and go out again. This needs a loop in `dispatch_trucks` that re-runs loading for the packages
   still at the hub whenever a driver comes back.
2. **Compare routes on round-trip miles.** Routes are compared on one-way miles, because the
   program only decides later whether a truck drives back to the hub. I would plan the "return to
   hub" decision first, so routes for returning trucks are scored with the drive home included.
3. **Move the scenario settings into a file.** The number of trucks, drivers, start time and the
   package 9 correction are constants in `main.py`. A small settings CSV would let a dispatcher in
   another city change them without editing code. Address corrections could also be entered while
   the program is running.
4. **Add automated tests.** I would add unit tests for the hash table (collisions, resizing,
   updates) and scenario tests that run the planner on edited package files. The validation report
   would become an automatic pass/fail check.

## H. Verification of the data structure

The solution uses a **hash table with separate chaining** (`ChainingHashTable` in `hash_table.py`),
written without dictionaries or extra libraries.

| Requirement | How the hash table meets it |
|---|---|
| Insert by package ID | `insert(key, value)` takes the package ID as the key. The value is a `Package` object holding the delivery address, deadline, city, zip code, weight and delivery status, including the delivery time. Inserting an existing ID updates it, so there are no duplicates. |
| Look up by package ID | `lookup(key)` returns the package. `lookup_package()` in `main.py` returns each data component, with the status and time, for any time of day. |
| Efficient | Insert and look-up are O(1) on average. Only the one bucket the ID hashes to is searched. |
| Handles collisions | Each bucket is a list, so two IDs that hash to the same bucket are stored side by side. |
| Grows with the data | When items ÷ buckets exceeds 1.0, the table doubles and re-hashes. For 40 packages it grows from 10 to 40 buckets, so each bucket holds about one package. |
| No dictionaries | Built only from Python lists and `hash()`. Addresses are also mapped to distance-matrix rows with the same hash table. |

### H1. Two other data structures that could meet the same requirements

1. **A self-balancing binary search tree** (such as an AVL tree) keyed by package ID.
2. **A direct-address table**: a plain list where the package with ID *n* is stored at index *n*.

### H1a. How each differs from the hash table

**Self-balancing binary search tree:**

- Look-up and insert take O(log n) instead of the hash table's average O(1).
- The tree keeps the packages **sorted by ID**, so "list all packages in order" needs no sort. The
  hash table has to sort its keys for ordered output.
- There are no collisions or resizing. Instead, the tree rotates nodes to stay balanced, which makes
  insert harder to write correctly.
- It uses one node, with child pointers, per package rather than a list of buckets.

**Direct-address table:**

- Look-up is always O(1), with no hashing and no collisions, because the ID *is* the index.
- It only works when IDs are small, non-negative integers. A hash table accepts any hashable key,
  which is why the same class also maps street addresses to matrix rows.
- Its memory is proportional to the **largest ID**, not the number of packages. IDs like 1, 2 and
  9,000,000 would waste almost all of the list. The hash table's memory follows the number of
  packages actually stored.

## I. Sources

Keep only the sources you actually used, and cite them in the text where you use them (for example
"(Croes, 1958)" in F3).

- Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to algorithms*
  (4th ed.). MIT Press.
- Croes, G. A. (1958). A method for solving traveling-salesman problems. *Operations Research, 6*(6),
  791–812.
- Kirkpatrick, S., Gelatt, C. D., & Vecchi, M. P. (1983). Optimization by simulated annealing.
  *Science, 220*(4598), 671–680.
- Python Software Foundation. (n.d.). *datetime — Basic date and time types*. Python 3
  documentation. https://docs.python.org/3/library/datetime.html

If you did not quote, paraphrase or summarize any source, say so explicitly (for example, "No
sources were used.").
