#!/usr/bin/env python3
'''Environmental footprint tests.

Run Batsim with --environmental-footprint-dynamic and verify that
*_carbon_footprint.csv uses the new zone-aware schema:
  - Has a "zone" column.
  - event_type values are "mix", "ci", or "wi" (not old chars 's', 'e', 'p').
  - One row per environmental-trace update, not per job/pstate event.
'''
import os
import subprocess
import time
import pandas as pd
from helper import create_dir_rec_if_needed

SCRIPT_DIR      = os.path.dirname(os.path.realpath(__file__))
BATSIM_DIR      = os.path.realpath(os.path.join(SCRIPT_DIR, '..'))
CARBON_PLATFORM = os.path.join(BATSIM_DIR, 'platforms', 'carbon_footprint_platform_homogeneous.xml')
ENV_TRACE       = os.path.join(BATSIM_DIR, 'events',    'test_env_trace.csv')
WORKLOAD        = os.path.join(BATSIM_DIR, 'workloads',  'test_delays.json')

SIMULATION_TIMEOUT = 60   # seconds


def _run_sim(test_name, port):
    '''Launch batsim + batsched for the environmental-footprint test and return output_dir.'''
    output_dir = os.path.abspath(f'test-out/{test_name}')
    create_dir_rec_if_needed(output_dir)
    export_prefix = os.path.join(output_dir, 'batres')
    socket = f'tcp://localhost:{port}'

    batsim_cmd = [
        'batsim',
        '-p', CARBON_PLATFORM,
        '-w', WORKLOAD,
        '--energy',
        '--environmental-footprint-dynamic', ENV_TRACE,
        '-e', export_prefix,
        '-s', socket,
    ]
    batsched_cmd = ['batsched', '-v', 'fcfs_fast', '-s', socket]

    batsim_log  = open(os.path.join(output_dir, 'batsim.log'),  'w')
    batsched_log = open(os.path.join(output_dir, 'batsched.log'), 'w')

    batsim_proc = subprocess.Popen(batsim_cmd,  stdout=batsim_log,  stderr=subprocess.STDOUT)
    time.sleep(3)
    assert batsim_proc.poll() is None, 'Batsim failed to start'

    batsched_proc = subprocess.Popen(batsched_cmd, stdout=batsched_log, stderr=subprocess.STDOUT)
    time.sleep(1)
    batsched_rc = batsched_proc.poll()
    assert batsched_rc in (None, 0), f'Batsched failed to start (rc={batsched_rc})'

    deadline = time.time() + SIMULATION_TIMEOUT
    while time.time() < deadline:
        if batsim_proc.poll() is not None and batsched_proc.poll() is not None:
            break
        time.sleep(0.5)
    else:
        batsim_proc.terminate()
        batsched_proc.terminate()
        batsim_log.close()
        batsched_log.close()
        raise TimeoutError(f'Simulation timed out after {SIMULATION_TIMEOUT}s')

    batsim_log.close()
    batsched_log.close()
    assert batsim_proc.returncode == 0,   f'Batsim exited with rc={batsim_proc.returncode}'
    assert batsched_proc.returncode == 0, f'Batsched exited with rc={batsched_proc.returncode}'
    return output_dir


def test_env_footprint_csv_schema():
    '''The carbon-footprint CSV must have the new zone-aware header and string event types.'''
    output_dir = _run_sim('env-footprint-schema', port=28000)
    csv_path = os.path.join(output_dir, 'batres_carbon_footprint.csv')
    assert os.path.isfile(csv_path), f'Output file not found: {csv_path}'

    df = pd.read_csv(csv_path)

    assert 'zone' in df.columns, f'"zone" column missing. Got: {list(df.columns)}'

    old_types = {'s', 'e', 'p'}
    actual_types = set(df['event_type'].unique())
    assert not (actual_types & old_types), \
        f'Old single-char event types still present: {actual_types & old_types}'

    expected_types = {'mix', 'ci', 'wi'}
    assert actual_types <= expected_types, \
        f'Unexpected event_type values: {actual_types - expected_types}'


def test_env_footprint_rows_match_trace():
    '''Number of CSV rows must equal the number of lines in the env trace (excluding header).'''
    output_dir = _run_sim('env-footprint-rows', port=28001)
    csv_path = os.path.join(output_dir, 'batres_carbon_footprint.csv')
    df = pd.read_csv(csv_path)

    with open(ENV_TRACE) as f:
        trace_data_lines = sum(1 for line in f) - 1  # subtract header

    assert len(df) == trace_data_lines, (
        f'CSV has {len(df)} rows but trace file has {trace_data_lines} data lines'
    )


def test_env_footprint_zone_column_values():
    '''All CSV rows must reference zone "AS0" matching the platform.'''
    output_dir = _run_sim('env-footprint-zone', port=28002)
    csv_path = os.path.join(output_dir, 'batres_carbon_footprint.csv')
    df = pd.read_csv(csv_path)

    zones = set(df['zone'].unique())
    assert zones == {'AS0'}, f'Expected only zone "AS0", got: {zones}'


def _expected_intensities_from_trace(trace_file):
    '''Parse the env trace and compute expected (ci, wi) after each update.

    The intensity reported for an update event is the weighted average of the
    per-source intensities using the *current* mix fractions at the moment that
    update fires.  Returns a list of (timestamp, zone, event_type, ci, wi).
    '''
    mix    = {}   # source → fraction (0–1)
    ci_map = {}   # source → gCO2e / kWh
    wi_map = {}   # source → L / kWh
    results = []

    with open(trace_file) as f:
        next(f)  # skip header
        for line in f:
            parts = line.strip().split(',', 3)
            if len(parts) < 4:
                continue
            ts   = float(parts[0])
            zone = parts[1].strip('"')
            prop = parts[2].strip('"')
            val  = parts[3].strip('"')

            vmap = {}
            for pair in val.split(';'):
                k, v = pair.split(':')
                vmap[k.strip()] = float(v.strip())

            if prop == 'energy_mix':
                total = sum(vmap.values())
                mix = {k: v / total for k, v in vmap.items()}
            elif prop == 'carbon_intensity':
                ci_map = vmap
            elif prop == 'water_intensity':
                wi_map = vmap

            ci = sum(mix.get(s, 0.0) * ci_map.get(s, 0.0) for s in mix) if mix else 0.0
            wi = sum(mix.get(s, 0.0) * wi_map.get(s, 0.0) for s in mix) if mix else 0.0

            etype = {'energy_mix': 'mix', 'carbon_intensity': 'ci', 'water_intensity': 'wi'}[prop]
            results.append((ts, zone, etype, ci, wi))

    return results


def test_env_footprint_intensity_values():
    '''Intensity columns must equal the weighted-average computed from the trace file.

    For each CSV row the carbon_intensity and water_intensity values are the dot
    product of the current energy-mix fractions and the per-source intensities.
    This test verifies that arithmetic independently, and also checks that the
    cumulative footprint columns never decrease.
    '''
    output_dir = _run_sim('env-footprint-values', port=28003)
    csv_path = os.path.join(output_dir, 'batres_carbon_footprint.csv')
    df = pd.read_csv(csv_path)

    expected = _expected_intensities_from_trace(ENV_TRACE)

    assert len(df) == len(expected), (
        f'Row count mismatch: CSV has {len(df)} rows, trace gives {len(expected)}'
    )

    tol = 1e-4
    for i, (exp_ts, _, exp_type, exp_ci, exp_wi) in enumerate(expected):
        row = df.iloc[i]
        assert abs(row['time'] - exp_ts) < tol, \
            f'Row {i}: time expected={exp_ts}, got={row["time"]}'
        assert row['event_type'] == exp_type, \
            f'Row {i}: event_type expected={exp_type!r}, got={row["event_type"]!r}'
        assert abs(row['carbon_intensity(gCO2e/kWh)'] - exp_ci) < tol, \
            f'Row {i} ({exp_type}@t={exp_ts}): ci expected={exp_ci:.6f}, got={row["carbon_intensity(gCO2e/kWh)"]:.6f}'
        assert abs(row['water_intensity(L/kWh)'] - exp_wi) < tol, \
            f'Row {i} ({exp_type}@t={exp_ts}): wi expected={exp_wi:.6f}, got={row["water_intensity(L/kWh)"]:.6f}'

    # Cumulative footprint must never decrease between consecutive rows.
    assert (df['carbon_footprint(gCO2e)'].diff().iloc[1:] >= 0).all(), \
        'carbon_footprint(gCO2e) decreased between rows'
    assert (df['water_footprint(L)'].diff().iloc[1:] >= 0).all(), \
        'water_footprint(L) decreased between rows'
