# WGUPS Routing Program: Written Answers (DRAFT)

> **This is a starting draft, not submission text.** WGU runs every submission through a
> similarity checker and expects original work. Rewrite each section in your own words, check
> every claim against your own run of the program, and keep only the sources you actually used.
> Every number below comes from running the program on the provided data (`python main.py --summary`
> and the `--time` reports).

---

## F1. Strengths of the algorithm

The solution uses a **constraint-aware greedy algorithm**. Packages are loaded onto trucks by rules
(most-constrained first, then a "nearest cluster" rule for end-of-day packages). Each truck's stops
are then ordered with the **nearest-neighbor heuristic**, trying three variants (plain,
deadline-first, earliest-deadline-first) and keeping the shortest route that meets every deadline.

**Strength 1: it is fast and scales well.** Nearest neighbor chooses each stop with one pass over the
packages still on the truck, so ordering one truck's route is O(k²) for k packages. The whole day
(loading, dispatch, routing and validation) runs in a fraction of a second for 40 packages. The
running time grows only polynomially as packages are added. Checking every possible order of k
stops (k! routes) becomes impossible after a few dozen stops.

**Strength 2: it adjusts itself at every step.** Each choice depends on where the truck is right now
and which packages are still on board. No fixed route is written into the code. If a package is
added, an address changes, or a delay moves a departure time, the same code builds a new route and
re-validates it. Trying three variants for each truck and keeping the best on-time one lets the
algorithm trade distance against urgency automatically. On this data plain nearest neighbor was
chosen for all three trucks, because it met every deadline with the fewest miles. On truck 3 all
three variants produced the same route.

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
| Every deadline met | Deadline packages that are at the hub at 8:00 go on truck 1 (leaves 8:00). The delayed deadline packages 6 and 25 go on truck 2, which leaves at 9:05 as soon as they arrive. Each truck keeps the shortest of its three route variants that has no late package | 14 deadline packages on time. Package 15 (9:00 AM) delivered 8:13 AM. Closest call: package 25 (10:30 AM) delivered 10:17 AM on truck 2 |
| Trucks average 18 mph; delivery and loading take no time | Every leg's time is miles ÷ 18 mph. A stop adds no extra time | Truck 1's 34.0 miles take 1 h 53 min (8:00 to 9:53) |
| Distances are the same in both directions | The triangular distance table is mirrored into a full matrix | The matrix lookup gives A→B = B→A |
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
2. **Simulated annealing** (Kirkpatrick et al., 1983)

Both would reuse the same truck loading and dispatch rules. Only the route-ordering step would
change, so all the scenario constraints (truck restrictions, delays, bundles, package 9) are met the
same way. Both would start from the current on-time nearest-neighbor route and only ever keep an
improved route that is still on time. The result can never be worse than the route used now, which
already meets every requirement.

### F3a. How each differs from the algorithm used

**2-opt** starts from a complete route, for example the nearest-neighbor route. It then repeatedly
picks two edges, reverses the section of the route between them, and keeps the change if the route
gets shorter and stays on time. It stops when no swap helps (Croes, 1958).

| | Nearest neighbor (used) | 2-opt |
|---|---|---|
| How it builds a route | Constructive: grows the route one stop at a time and never revisits a choice | Improvement: rewrites a whole existing route |
| Looks at | Only the next stop | Pairs of edges across the whole route |
| Can it undo a bad early choice? | No | Yes: crossings and long back-tracks get removed |
| Cost | O(k²) for one route | O(k²) swaps per pass, each re-checked against the deadlines in O(k), so up to O(k³) per pass, repeated until no swap helps |

**Simulated annealing** also improves a complete route with small random changes, such as swapping
two stops or reversing a section. Unlike 2-opt, it sometimes **accepts a worse route on purpose**.
How likely that is depends on a "temperature" that starts high and slowly cools (Kirkpatrick et al.,
1983). Routes that miss a deadline are never accepted. The best on-time route seen so far is kept
and returned at the end.

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
| Efficient | Insert and look-up are O(1) on average. Only the one bucket the ID hashes to is searched (Cormen et al., 2022). |
| Handles collisions | Each bucket is a list ("separate chaining"), so two IDs that hash to the same bucket are stored side by side. |
| Grows with the data | When items ÷ buckets exceeds 1.0, the table doubles and re-hashes. For 40 packages it grows from 10 to 40 buckets, so each bucket holds about one package. |
| No dictionaries | Built only from Python lists and `hash()`. Addresses are also mapped to distance-matrix rows with the same hash table. |

### H1. Two other data structures that could meet the same requirements

1. **A self-balancing binary search tree** (such as an AVL tree) keyed by package ID.
2. **A sorted list with binary search**: a Python list of packages kept in package-ID order.

Both meet the same requirements. Each can insert a package under its ID with all six data
components, and look the package up by ID to return those components and the timestamped
status. Neither uses a dictionary.

### H1a. How each differs from the hash table

**Self-balancing binary search tree:**

- Look-up and insert take O(log n) instead of the hash table's average O(1) (Cormen et al., 2022).
- The tree keeps the packages **sorted by ID**, so "list all packages in order" needs no sort. The
  hash table has to sort its keys for ordered output.
- There are no collisions or resizing. Instead, the tree rotates nodes to stay balanced, which makes
  insert harder to write correctly.
- It uses one node, with child pointers, per package rather than a list of buckets.

**Sorted list with binary search:**

- Look-up is O(log n): binary search halves the part of the list to check each time. The hash
  table goes straight to one bucket in O(1) on average.
- Insert is O(n), because every package after the new one has to shift one place to keep the list
  sorted. The hash table inserts in O(1) on average with no shifting.
- It needs no hash function, no buckets and no resizing, and it is always in ID order. That makes
  it the simplest of the three to write and to print in order.
- It stores the packages back to back in one list, with no empty buckets. The hash table keeps
  extra buckets so that its chains stay short.

## I. Sources

Keep only the sources you actually used, and cite each one in the text wherever you quote,
paraphrase or summarize it (as in F3a, H and H1a above). If course material shaped your design,
such as the C950 zyBooks or a WGU webinar, cite it too.

- Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to algorithms*
  (4th ed.). MIT Press.
- Croes, G. A. (1958). A method for solving traveling-salesman problems. *Operations Research, 6*(6),
  791–812. https://doi.org/10.1287/opre.6.6.791
- Kirkpatrick, S., Gelatt, C. D., Jr., & Vecchi, M. P. (1983). Optimization by simulated annealing.
  *Science, 220*(4598), 671–680. https://doi.org/10.1126/science.220.4598.671

If you did not quote, paraphrase or summarize any source, say so explicitly (for example, "No
sources were used.").
