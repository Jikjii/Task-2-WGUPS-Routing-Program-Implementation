# WGUPS Routing Program (C950 Task 2)

This program plans one day of Western Governors University Parcel Service (WGUPS) deliveries in
Salt Lake City. Three trucks and two drivers deliver 40 packages. Every package is on time,
every special note is honored, and the trucks drive **93.5 miles in total** (the limit is 140).

It is written in plain Python 3 with only the standard library. No `pip install` is needed, and
it uses no dictionaries. Package storage uses a hash table written from scratch.

> **Before submitting:** replace `000000000` on line 1 of `main.py` with your WGU student ID.

## How to run

```bash
python main.py                              # interactive menu (the supervisor interface)
python main.py --time 9:00                  # status of ALL packages, by truck, at 9:00 AM
python main.py --time 12:30 PM              # 12-hour times work too (or 24-hour: 12:30, 13:05)
python main.py --package 9 --time 10:30     # every data component of one package at a time
python main.py --summary                    # rule check, route report, total mileage
```

The menu options:

1. Status of **all** packages at any time, grouped by truck, with each package's delivery status
   (Delayed, At the hub, En route or Delivered, each with its time) and the mileage driven so far.
2. Status of **one** package at any time (address, deadline, city, zip, weight, status and time).
3. End-of-day route report and the total mileage for all trucks.
4. Exit.

## Results

| Truck | Driver | Leaves hub | Packages | Miles | Day ends |
|------:|:------:|:----------:|:--------:|------:|:--------|
| 1 | 1 | 8:00 AM  | 16 | 34.0 | back at the hub 9:54 AM (driver 1 then takes truck 3) |
| 2 | 2 | 9:05 AM  | 16 | 31.7 | last delivery 10:51 AM |
| 3 | 1 | 10:20 AM | 8  | 27.8 | last delivery 11:53 AM |
| **Total** | | | **40** | **93.5** | all 40 delivered by 11:53 AM |

All ten rule checks print `[PASS]` at start-up:

- every package delivered
- all 14 deadlines met (the closest margin is package 25, 13 minutes early)
- 16 or fewer packages per truck
- packages 3, 18, 36 and 38 on truck 2
- delayed packages 6, 25, 28 and 32 leave at 9:05, when they arrive
- packages 13, 14, 15, 16, 19 and 20 together on truck 1
- package 9 leaves only once the 10:20 fix is known, and goes to 410 S State St
- no departure before 8:00
- never more than two trucks on the road, and a driver brings a truck back before taking another
- total mileage under 140

## How it works

| Step | File | What happens |
|------|------|--------------|
| Load data | `data_loader.py` | `packages.csv` goes into `ChainingHashTable` (key = package ID). The triangular distance table is mirrored into a full matrix. |
| Read notes | `package.py` | Each special note becomes a constraint: required truck, hub arrival time, bundle partners, wrong address. |
| Load trucks | `routing.py` | Union-find joins the "must be delivered with" packages into bundles. Bundles are loaded most-constrained first: required truck, then delayed, then wrong address, then deadline. End-of-day packages go to the nearest cluster. |
| Dispatch | `routing.py` | The most urgent truck leaves first. The third truck waits for a driver (truck 1 drives back), and it waits for package 9's 10:20 address fix. |
| Route | `routing.py` | Three nearest-neighbor variants (plain, deadline-first, earliest-deadline-first) are tried for each truck. The shortest on-time route wins. |
| Validate | `validation.py` | Every scenario rule is re-checked from the recorded times and printed as `[PASS]` / `[FAIL]`. |
| Interface | `main.py` | Status at any time is replayed from each package's departure and delivery timestamps. |

The full design is explained in the comments at the top of each file. `routing.py` has the algorithm
walkthrough and its Big-O analysis.

## Files

```
main.py            entry point, settings, look-up function, menu and reports (student ID on line 1)
hash_table.py      ChainingHashTable: self-resizing hash table with insert / lookup / remove
package.py         Package class, special-note parsing, status at any time
truck.py           Truck class and its stops, mileage at any time
distance_table.py  address -> matrix row lookup and distances
data_loader.py     reads the CSV files
routing.py         loading, dispatch and nearest-neighbor routing (the core algorithm)
validation.py      re-checks every scenario rule
time_utils.py      parse and format clock times
data/              packages.csv, addresses.csv, distances.csv (from the WGUPS spreadsheets)
screenshots/       D1 (9:00), D2 (10:00), D3 (12:30 PM), E (full run), interface demo, as .png and .txt
docs/              draft of the written answers for F-I
```

## Screenshots (requirements D and E)

| Requirement | Time window | File |
|-------------|-------------|------|
| D1 | 8:35-9:25 AM | `screenshots/D1_status_0900.png` |
| D2 | 9:35-10:25 AM | `screenshots/D2_status_1000.png` |
| D3 | 12:03-1:12 PM | `screenshots/D3_status_1230.png` |
| D  (interface) | any | `screenshots/D_interface_package_lookup.png` |
| E  (completed run, total mileage) | - | `screenshots/E_completed_run_total_mileage.png` |

These PNGs are **rendered images of the program's real output**, not captures of a terminal window.
The text is unchanged (the `.txt` next to each one is the raw output), but they were made in this
cloud session, not on your computer. **For your submission, run the same commands on your own
machine and take real screenshots.** The output is identical on every run, so the PNGs show you
exactly what to expect.

## Submitting

- **C1:** put your student ID on line 1 of `main.py`.
- **Code:** zip the project folder without `__pycache__/`. The `screenshots/` and `docs/` folders are
  not code, so leave them out.
- **Screenshots (D1-D3, E):** take them yourself, and collect them in one PDF, as the task asks.
- **Written answers (F-J):** WGU wants a Word document. Rewrite `docs/written_answers_draft.md` in
  your own words. The task requires original work and runs a similarity check.
