# Battery Dataset

This directory contains the battery data used by **BATRIS (Battery Traceability & Reliability Intelligence System)** for battery health, reliability, and lifecycle analysis.

## Dataset Overview

The project uses the **NASA Li-ion Battery Aging Dataset**, which contains battery cycling data collected at the **NASA Ames Research Center**. The data includes repeated charge, discharge, and impedance operations performed on lithium-ion battery cells.

The current repository uses the following battery files:

* `B0005.mat`
* `B0006.mat`
* `B0007.mat`
* `B0018.mat`

The dataset provides measurements such as **voltage, current, temperature, cycle information, discharge capacity, and impedance-related data**, which are used by BATRIS for battery degradation and health analysis.

## Download Dataset

The complete dataset and information about the NASA Li-ion Battery Aging Dataset are available from the NASA Open Data portal:

**https://data.nasa.gov/dataset/li-ion-battery-aging-datasets**

Download the dataset and place the required `.mat` battery files in the project's dataset directory.

## Data Format

The battery data is stored in **MATLAB `.mat` files**. These files are processed by the project's data-processing pipeline before being used by the battery health and prediction models.

## Note

The repository currently includes a selected set of NASA battery files for development and testing. The original NASA dataset contains additional battery experiments and operating conditions.
