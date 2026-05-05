# Environmental Trace CSV Format

This document describes the standard format for environmental trace CSV files used in Batsim/SimGrid to simulate dynamic energy grids and environmental impacts based on the component model (Off-site, On-site, and Embodied).

## Format Overview

Unlike simple time-series files, this trace is **Event-Based**. Rows represent specific *changes* to the environment state. You only need to list a row when a value actually changes.

The CSV file must contain the following columns, strictly in this order:

1.  **timestamp**: Unix timestamp or simulation seconds (when the event occurs).
2.  **host_id**: The ID of the host (or region/cluster) to be updated.
3.  **property_name**: The specific attribute being updated.
4.  **new_value**: The new numeric data for that property.

## Supported Properties

The trace directly feeds consolidated intensities and infrastructure metrics to the simulation, avoiding complex string parsing at runtime.

| Property Name | Description | Value Format Example |
| :--- | :--- | :--- |
| `carbon_intensity` | Updates the consolidated **off-site** Carbon intensity of the grid (gCO₂eq/kWh). | `500.0` |
| `water_intensity` | Updates the consolidated **off-site** Water intensity of the grid (L/kWh). | `15.5` |
| `wue` | Updates the **on-site** Water Usage Effectiveness (L/kWh), which usually fluctuates based on weather/cooling needs. | `1.8` |
| `pue` | Updates the datacenter's Power Usage Effectiveness. | `1.2` |

## Technical Specifications

* **Delimiter:** Comma (`,`).
* **Ordering:** Rows must be strictly ordered chronologically by the `timestamp`.
* **Update Behavior:** * When updating any property, the new value immediately **overwrites** the previous one.
    * The environmental footprint plugin automatically calculates the incremental accumulation using the *old* value for the elapsed time interval, before applying the *new* value for future calculations.
* **Units:**
    * Energy is handled internally in Joules and converted to kWh to apply the intensities.
    * Carbon is expressed in grams (g).
    * Water is expressed in liters (L).

## Usage Example

```csv
timestamp,host_id,property_name,new_value
0,Earth,carbon_intensity,120.5
0,Earth,water_intensity,15.2
0,Earth,wue,0.8
0,Earth,pue,1.15
3600,Earth,carbon_intensity,150.0
3600,Earth,wue,1.2
7200,Earth,carbon_intensity,200.0
7200,Earth,water_intensity,18.0
14400,Earth,wue,0.4