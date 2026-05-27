#!/usr/bin/env python3
'''Environmental footprint tests.

Run Batsim with --environmental-footprint-dynamic and verify that
*_carbon_footprint.csv uses the job/pstate-triggered, per-component schema:
  - Has a "zone" column.
  - event_type values are single chars 's' (job start), 'e' (job end),
    or 'p' (pstate change) — mirroring EnergyConsumptionTracer.
  - One row per zone per job/pstate event, NOT per environmental-trace update.
  - Per-component footprint columns: operational/embodied for carbon,
    onsite/offsite/embodied for water, plus per-component totals.
'''
import json
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

EXPECTED_COLUMNS = [
    'time', 'zone', 'event_type',
    'carbon_operational(gCO2e)', 'carbon_embodied(gCO2e)', 'carbon_total(gCO2e)',
    'water_onsite(L)', 'water_offsite(L)', 'water_embodied(L)', 'water_total(L)',
]


def _kill_proc(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    except Exception:
        pass


def _run_sim(test_name, port):
    '''Launch batsim + batsched for the environmental-footprint test and return output_dir.

    Subprocesses are always killed on exit (success, failure, or timeout) so a failing
    test never leaks daemons that would corrupt subsequent tests on the same machine.
    '''
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

    batsim_proc = None
    batsched_proc = None
    try:
        batsim_proc = subprocess.Popen(batsim_cmd, stdout=batsim_log, stderr=subprocess.STDOUT)
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
            raise TimeoutError(f'Simulation timed out after {SIMULATION_TIMEOUT}s')

        assert batsim_proc.returncode == 0,   f'Batsim exited with rc={batsim_proc.returncode}'
        assert batsched_proc.returncode == 0, f'Batsched exited with rc={batsched_proc.returncode}'
        return output_dir
    finally:
        _kill_proc(batsim_proc)
        _kill_proc(batsched_proc)
        batsim_log.close()
        batsched_log.close()


def _read_csv(output_dir):
    csv_path = os.path.join(output_dir, 'batres_carbon_footprint.csv')
    assert os.path.isfile(csv_path), f'Output file not found: {csv_path}'
    return pd.read_csv(csv_path), csv_path


def test_env_footprint_csv_schema():
    '''The carbon-footprint CSV must have the new per-component header and char event types.'''
    output_dir = _run_sim('env-footprint-schema', port=28000)
    df, _ = _read_csv(output_dir)

    assert list(df.columns) == EXPECTED_COLUMNS, \
        f'Header mismatch.\nExpected: {EXPECTED_COLUMNS}\nGot:      {list(df.columns)}'

    actual_types = set(df['event_type'].unique())
    allowed_types = {'s', 'e', 'p'}
    assert actual_types <= allowed_types, \
        f'Unexpected event_type values: {actual_types - allowed_types}'

    # At least job-start and job-end events must appear (the workload has jobs).
    assert {'s', 'e'} <= actual_types, \
        f'Expected at least start/end events, got: {actual_types}'


def test_env_footprint_zone_column_values():
    '''All CSV rows must reference zone "AS0" matching the platform.'''
    output_dir = _run_sim('env-footprint-zone', port=28002)
    df, _ = _read_csv(output_dir)

    zones = set(df['zone'].unique())
    assert zones == {'AS0'}, f'Expected only zone "AS0", got: {zones}'


def test_env_footprint_row_count_matches_jobs_and_pstates():
    '''CSV row count must equal (start+end per job + pstate changes) * #zones.'''
    output_dir = _run_sim('env-footprint-rows', port=28001)
    df, _ = _read_csv(output_dir)

    with open(WORKLOAD) as f:
        nb_jobs = len(json.load(f)['jobs'])

    nb_starts  = int((df['event_type'] == 's').sum())
    nb_ends    = int((df['event_type'] == 'e').sum())
    nb_pstates = int((df['event_type'] == 'p').sum())
    nb_zones   = df['zone'].nunique()

    # One start and one end row per job per zone.
    assert nb_starts == nb_jobs * nb_zones, \
        f'Expected {nb_jobs * nb_zones} start rows, got {nb_starts}'
    assert nb_ends == nb_jobs * nb_zones, \
        f'Expected {nb_jobs * nb_zones} end rows, got {nb_ends}'

    # Total rows == start + end + pstate rows (no other event types).
    assert len(df) == nb_starts + nb_ends + nb_pstates, \
        f'Row count {len(df)} != s({nb_starts}) + e({nb_ends}) + p({nb_pstates})'


def test_env_footprint_per_zone_cumulative_monotonic():
    '''Per-zone cumulative footprint columns must never decrease over time.'''
    output_dir = _run_sim('env-footprint-monotonic', port=28003)
    df, _ = _read_csv(output_dir)

    cumulative_cols = [
        'carbon_operational(gCO2e)', 'carbon_embodied(gCO2e)', 'carbon_total(gCO2e)',
        'water_onsite(L)', 'water_offsite(L)', 'water_embodied(L)', 'water_total(L)',
    ]

    for zone, group in df.groupby('zone'):
        group = group.sort_values('time').reset_index(drop=True)
        for col in cumulative_cols:
            diffs = group[col].diff().iloc[1:]
            # Allow tiny negative noise from long-double → double round-trip.
            assert (diffs >= -1e-6).all(), \
                f'Zone {zone}: column {col!r} decreased between rows.\n{group[["time","event_type",col]]}'


def test_env_footprint_component_totals_consistent():
    '''carbon_total ≈ operational + embodied; water_total ≈ onsite + offsite + embodied.'''
    output_dir = _run_sim('env-footprint-components', port=28004)
    df, _ = _read_csv(output_dir)

    tol = 1e-3
    carbon_diff = (df['carbon_total(gCO2e)']
                   - df['carbon_operational(gCO2e)']
                   - df['carbon_embodied(gCO2e)']).abs()
    assert (carbon_diff < tol).all(), \
        f'carbon_total != operational + embodied (max diff: {carbon_diff.max()})'

    water_diff = (df['water_total(L)']
                  - df['water_onsite(L)']
                  - df['water_offsite(L)']
                  - df['water_embodied(L)']).abs()
    assert (water_diff < tol).all(), \
        f'water_total != onsite + offsite + embodied (max diff: {water_diff.max()})'
