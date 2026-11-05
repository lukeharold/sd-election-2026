# San Diego County election maps, Nov. 3, 2026

Precinct-by-precinct Datawrapper maps of unofficial San Diego County results for Governor, Props 39-42 and the 48th-52nd congressional districts.

A GitHub Action checks the [Registrar of Voters' results file](https://www.livevoterturnout.com/ENR/sandiegocaenr/25/en/Index_25.html) every 30 minutes from noon to midnight Pacific. When a new post appears, it rebuilds and republishes the maps.

**How margins work:** a precinct's margin is the percentage-point difference between the two options, using the votes counted in that precinct. Positive means the Democrat or Yes is ahead. Precincts with no votes counted are left off the map. `VBM-AV` rows have no precinct shape, so they count toward contest totals but don't appear on the maps.

## Files

- `update.py`: checks for a new post, runs the two scripts below, and records what was published
- `build_maps.py`: turns the results file into one CSV per map
- `push_datawrapper.py`: sends the data and wording to Datawrapper and publishes
- `boundaries/`: precinct shapes
- `datawrapper_charts.json`: the chart ID for each map
- `state/last_post.json`: the timestamp and vote totals of the last published post

## Running it by hand

```bash
python3 update.py --dry-run
```

Publishing needs a Datawrapper token in the `DATAWRAPPER_TOKEN` environment variable.
