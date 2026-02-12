# Environmental Trace CSV Format

This document describes the standard format for environmental trace CSV files used in Batsim/SimGrid to simulate dynamic energy grids and environmental impacts.

## Format Overview

Unlike simple time-series files, this trace is **Event-Based**. Rows represent specific *changes* to the environment state. You only need to list a row when a value actually changes.

The CSV file must contain the following columns in order:

1.  **timestamp**: Unix timestamp or simulation seconds (when the event occurs).
2.  **host_id**: The ID of the host (or cluster/region) to update.
3.  **property_name**: The specific attribute being updated.
4.  **new_value**: The new data string for that property.

### Supported Properties

| Property Name | Description | Value Format Example |
| :--- | :--- | :--- |
| `energy_mix` | Updates the % contribution of each source. | `"Hydro:80;Solar:20"` |
| `carbon_intensity` | Updates the Carbon intensity (gCO2eq/kWh) of sources. | `"Hydro:24;Solar:45"` |
| `water_intensity` | Updates the Water intensity (L/kWh) of sources. | `"Hydro:15;Solar:0.04"` |

## Specifications

* **Delimiter:** Comma (`,`)
* **Ordering:** Rows must be strictly ordered chronologically by `timestamp`.
* **Partial Updates:**
    * Updating `energy_mix` **resets** the current mix percentages but **preserves** the known carbon/water intensities of the sources.
    * Updating `carbon_intensity` or `water_intensity` **merges** the new values into the existing knowledge base without changing the active mix percentages.
        
        * Values set from sources not present in the energy mix will be discarded. 

## Example

```csv
timestamp,host_id,property_name,new_value
0,host_br_01,carbon_intensity,"Hydro:24;Solar:45;Gas:490"
0,host_br_01,water_intensity,"Hydro:15;Solar:0.04;Gas:0.8"
0,host_br_01,energy_mix,"Hydro:80;Solar:20;Gas:0"
3600,host_br_01,energy_mix,"Hydro:70;Solar:30;Gas:0"
7200,host_br_01,energy_mix,"Hydro:60;Solar:40;Gas:0"
172800,host_br_01,carbon_intensity,"Hydro:24;Solar:45"
172800,host_br_01,energy_mix,"Hydro:50;Solar:10;Gas:40"
360000,host_br_01,water_intensity,"Gas:5.3"
