# SPDX-FileCopyrightText: 2026 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""Fuel-cycle calculations shared by the Cyclus and DYMOND plugins.

Cyclus and DYMOND store their results in different formats, but WATTS asks the
same fuel-cycle questions of both.  Each plugin reads its simulator file and
converts the data into the small common structures in this module.  The shared
functions then apply the same units, selection rules, and fuel calculations.

These functions use ordinary NumPy arrays and do not import either simulator
plugin.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

from .enrichment_utils import enrichment_cascade


# DYMOND process times use a Julian year.  Defining it here keeps both plugins
# on the same time conversion when they report common WATTS results.
SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60


# Every common power result is reported in GW.  This table contains every unit
# previously accepted by either plugin.  EJ/yr and TWh/yr represent average
# power over a year, so they can also be converted to GW.
POWER_TO_GW = {
    "W": 1.0e-9,
    "KW": 1.0e-6,
    "KWE": 1.0e-6,
    "MW": 1.0e-3,
    "MWE": 1.0e-3,
    "GW": 1.0,
    "GWE": 1.0,
    "EJ/YR": 1.0e18 / (SECONDS_PER_YEAR * 1.0e9),
    "TWH/YR": 1.0e12 / (8766.0 * 1.0e9),
}


# Every common fuel-mass result is reported in kg.  The input file may use any
# of these accepted spellings, but callers always receive the same output unit.
MASS_TO_KG = {
    "G": 1.0e-3,
    "GRAM": 1.0e-3,
    "GRAMS": 1.0e-3,
    "KG": 1.0,
    "KILOGRAM": 1.0,
    "KILOGRAMS": 1.0,
    "T": 1.0e3,
    "TONNE": 1.0e3,
    "TONNES": 1.0e3,
    "METRIC TON": 1.0e3,
    "METRIC TONS": 1.0e3,
}

# Default assays and cascade splits.
NATURAL_ASSAY = 0.711E-2
TAILS_ASSAY = 0.250E-2
CASCADE_SPLITS = [0.1, 0.2]


def find_single_output(
    outputs: Iterable[Path],
    suffixes: Sequence[str],
    description: str,
) -> Path:
    """Find the one simulator output file with an accepted suffix.

    Parameters
    ----------
    outputs : iterable of pathlib.Path
        Files produced by one simulator run.
    suffixes : sequence of str
        Accepted file suffixes, with or without a leading period.
    description : str
        Plain-language file description used in error messages.

    Returns
    -------
    pathlib.Path
        The only output file with an accepted suffix.

    Raises
    ------
    ValueError
        If no matching file or more than one matching file is present.

    Notes
    -----
    A normal runtime error is used instead of ``assert`` because Python can
    disable assertions.  Users should always receive the same useful error.
    """

    accepted_suffixes = tuple(
        suffix.lower() if str(suffix).startswith(".")
        else f".{str(suffix).lower()}"
        for suffix in suffixes
    )
    matches = [
        Path(path)
        for path in outputs
        if Path(path).suffix.lower() in accepted_suffixes
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {description} output with suffix "
            f"{list(accepted_suffixes)}, found {len(matches)}: {matches}."
        )
    return matches[0]


@dataclass(frozen=True)
class FuelReceipt:
    """Fuel receipt data used by the shared enrichment calculation.

    Parameters
    ----------
    reactor : str
        Reactor type or Cyclus prototype name.
    time_index : int
        Position on the plugin's result time axis.
    material_mass : float
        Total delivered material mass in kg.  This is retained for checks; the
        enrichment calculation uses ``uranium_mass`` as its product mass.
    uranium_mass : float
        Uranium mass in kg in the received material.
    u235_mass : float
        U-235 mass in kg in the received material.

    Notes
    -----
    Cyclus builds this record from database tables, while DYMOND builds it from
    HDF5 process data.  The nonlinear cascade is calculated for each receipt
    before the results are added by time period.  This order matters when a
    reactor receives fuel with more than one assay in a reporting period.
    """

    reactor: str
    time_index: int
    material_mass: float
    uranium_mass: float
    u235_mass: float


def _standard_unit_name(unit: str) -> str:
    """Convert a unit spelling to the form used by the conversion tables.

    Parameters
    ----------
    unit : str
        Unit spelling supplied by a simulator input file or caller.

    Returns
    -------
    str
        Uppercase unit name with standard spacing around a slash.
    """

    # Removing spaces around the slash lets inputs such as ``"EJ / yr"`` use
    # the same table entry as ``"EJ/yr"`` without accepting ambiguous units.
    return str(unit).strip().upper().replace(" / ", "/")


def power_to_gw(values, unit: str) -> np.ndarray:
    """Convert power values to GW.

    Parameters
    ----------
    values : float or array-like
        Power values in ``unit``.
    unit : str
        Unit used by ``values``.

    Returns
    -------
    numpy.ndarray
        Power values in GW.  A scalar input produces a zero-dimensional
        NumPy array.

    Raises
    ------
    ValueError
        If ``unit`` is not in :data:`POWER_TO_GW`.
    """

    unit_name = _standard_unit_name(unit)
    try:
        factor = POWER_TO_GW[unit_name]
    except KeyError as exc:
        supported = ", ".join(sorted(POWER_TO_GW))
        raise ValueError(
            f"Unsupported power unit {unit!r}. Supported units: {supported}."
        ) from exc
    return np.asarray(values, dtype=float) * factor


def mass_to_kg(values, unit: str) -> np.ndarray:
    """Convert mass values to kg.

    Parameters
    ----------
    values : float or array-like
        Mass values in ``unit``.
    unit : str
        Unit used by ``values``.

    Returns
    -------
    numpy.ndarray
        Mass values in kg.  A scalar input produces a zero-dimensional NumPy
        array.

    Raises
    ------
    ValueError
        If ``unit`` is not in :data:`MASS_TO_KG`.
    """

    unit_name = _standard_unit_name(unit)
    try:
        factor = MASS_TO_KG[unit_name]
    except KeyError as exc:
        supported = ", ".join(sorted(MASS_TO_KG))
        raise ValueError(
            f"Unsupported mass unit {unit!r}. Supported units: {supported}."
        ) from exc
    return np.asarray(values, dtype=float) * factor


def select_reactors(
    reactors,
    available: Sequence[str],
) -> tuple[str, ...]:
    """Select reactors and check that every requested name exists.

    Parameters
    ----------
    reactors : str, sequence of str, or None
        Requested reactors.  ``None`` selects every available reactor.
    available : sequence of str
        Reactor names present in the simulator results.

    Returns
    -------
    tuple of str
        Requested reactor names with repeated names removed.  The caller's
        order is preserved.

    Raises
    ------
    ValueError
        If a requested reactor is not present in ``available``.
    """

    available_names = tuple(str(name) for name in available)
    if reactors is None:
        requested = available_names
    elif isinstance(reactors, str):
        requested = (reactors,)
    else:
        requested = tuple(str(name) for name in reactors)

    # A dictionary preserves insertion order, so it removes repeated names
    # without changing the order supplied by the caller.
    requested = tuple(dict.fromkeys(requested))
    unknown = [name for name in requested if name not in available_names]
    if unknown:
        raise ValueError(
            f"Unknown reactor(s): {unknown}. Available reactors: "
            f"{list(available_names)}."
        )
    return requested


def sum_reactor_series(
    series_by_reactor: Mapping[str, np.ndarray],
    reactors: Sequence[str],
    length: int,
) -> np.ndarray:
    """Add selected reactor time series.

    Parameters
    ----------
    series_by_reactor : mapping of str to numpy.ndarray
        One one-dimensional time series for each reactor.
    reactors : sequence of str
        Reactors to include in the sum.
    length : int
        Required number of time points in each series.

    Returns
    -------
    numpy.ndarray
        Sum of the selected reactor series.  An empty selection returns a zero
        array with ``length`` entries.

    Raises
    ------
    ValueError
        If a selected reactor has no series or a series has the wrong shape.
    """

    selected = []
    expected_shape = (int(length),)
    for reactor in reactors:
        if reactor not in series_by_reactor:
            raise ValueError(f"No series is available for reactor {reactor!r}.")
        values = np.asarray(series_by_reactor[reactor], dtype=float)
        if values.shape != expected_shape:
            raise ValueError(
                f"Series for reactor {reactor!r} has shape {values.shape}; "
                f"expected {expected_shape}."
            )
        selected.append(values)

    # NumPy returns the scalar 0.0 for an empty sum.  Handle that case directly
    # so both plugins return a time series even when no reactor is selected.
    if not selected:
        return np.zeros(expected_shape, dtype=float)
    return np.sum(np.stack(selected, axis=0), axis=0)


def format_reactor_results(
    series_by_reactor: Mapping[str, np.ndarray],
    reactors: Sequence[str],
    length: int,
    return_sum: bool,
):
    """Prepare reactor time series for a public plugin result.

    Parameters
    ----------
    series_by_reactor : mapping of str to numpy.ndarray
        One one-dimensional time series for each reactor.
    reactors : sequence of str
        Reactors to include in the returned result.
    length : int
        Required number of time points in each series.
    return_sum : bool
        Return one summed array when ``True``; otherwise return a dictionary
        with one array per reactor.

    Returns
    -------
    numpy.ndarray or dict of str to numpy.ndarray
        Summed time series or separate copies of the selected reactor series.

    Raises
    ------
    ValueError
        If a selected reactor has no series or a series has the wrong shape.
    """

    if return_sum:
        return sum_reactor_series(series_by_reactor, reactors, length)

    # Return new arrays so a caller can edit a result without changing cached
    # Cyclus data or the DYMOND data held by the reader.
    result = {}
    for reactor in reactors:
        if reactor not in series_by_reactor:
            raise ValueError(f"No series is available for reactor {reactor!r}.")
        values = np.asarray(series_by_reactor[reactor], dtype=float)
        if values.shape != (int(length),):
            raise ValueError(
                f"Series for reactor {reactor!r} has shape {values.shape}; "
                f"expected {(int(length),)}."
            )
        result[reactor] = np.array(values, copy=True)
    return result


def aggregate_calendar_years(
    values,
    init_year: int,
    init_month: int,
    how: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Combine monthly values by calendar year.

    Parameters
    ----------
    values : array-like
        Monthly data with time on the first axis.
    init_year : int
        Calendar year of the first monthly value.
    init_month : int
        Calendar month of the first value, from 1 through 12.
    how : {"sum", "max", "end", "mean", "avg"}
        Calculation to apply to the months in each calendar year.

    Returns
    -------
    years : numpy.ndarray
        Calendar-year labels for the returned data.
    yearly_values : numpy.ndarray
        Values combined by calendar year.  Partial first and last years are
        retained.

    Raises
    ------
    ValueError
        If ``values`` has no time axis, ``init_month`` is outside 1 through
        12, or ``how`` is not supported.

    Notes
    -----
    For ``"mean"`` or ``"avg"``, a partial year is averaged over the months
    represented in the input rather than divided by twelve.
    """

    array = np.asarray(values)
    if array.ndim == 0:
        raise ValueError("Monthly values must have a time dimension.")
    if not 1 <= int(init_month) <= 12:
        raise ValueError(f"init_month must be in [1, 12], got {init_month!r}.")
    if array.shape[0] == 0:
        return (
            np.zeros(0, dtype=int),
            np.zeros((0, *array.shape[1:]), dtype=array.dtype),
        )

    month_indices = int(init_month) - 1 + np.arange(array.shape[0])
    calendar_years = int(init_year) + month_indices // 12
    unique_years, first_indices = np.unique(calendar_years, return_index=True)
    blocks = np.split(array, first_indices[1:], axis=0)

    if how == "sum":
        aggregated = [block.sum(axis=0) for block in blocks]
    elif how == "max":
        aggregated = [block.max(axis=0) for block in blocks]
    elif how == "end":
        aggregated = [block[-1] for block in blocks]
    elif how in ("avg", "mean"):
        aggregated = [block.mean(axis=0) for block in blocks]
    else:
        raise ValueError(
            f"Unknown yearly aggregation {how!r}; expected sum, max, end, "
            "or mean."
        )

    return unique_years.astype(int), np.stack(aggregated, axis=0)


def _check_cascade_splits(
    cascade_splits=CASCADE_SPLITS,
    natural_assay: float = NATURAL_ASSAY,
) -> list[float]:
    """Check and prepare enrichment-stage assay limits.

    Parameters
    ----------
    cascade_splits : sequence of float or None
        Upper product-assay limits for the enrichment stages.  ``None`` uses
        the WATTS defaults ``[0.1, 0.2]``.  An empty sequence requests one
        stage with no finite upper limit.
    natural_assay : float
        U-235 assay of natural uranium, expressed as a fraction.

    Returns
    -------
    list of float
        Checked stage limits in ascending order.

    Raises
    ------
    ValueError
        If a limit is outside the allowed assay range, limits are not strictly
        increasing, or infinity is mixed with finite limits.
    """
    if cascade_splits is None:
        cascade_splits = CASCADE_SPLITS
    splits = [float(value) for value in cascade_splits]

    # The lower-level enrichment function represents a single stage with an
    # infinite upper assay limit.
    if not splits:
        return [np.inf]
    if splits == [np.inf]:
        return splits
    if not all(np.isfinite(value) for value in splits):
        raise ValueError(
            "cascade_splits must be finite, except for the one-stage [inf] "
            "request."
        )
    if any(not natural_assay < value < 1.0 for value in splits):
        raise ValueError(
            "Every cascade split must be above the natural assay and below "
            "one."
        )
    if any(right <= left for left, right in zip(splits, splits[1:])):
        raise ValueError("cascade_splits must be strictly increasing.")
    return splits


def calculate_fuel_resources(
    receipts: Iterable[FuelReceipt],
    reactors: Sequence[str],
    n_times: int,
    natu_assay: float = NATURAL_ASSAY,
    tails_assay: float = TAILS_ASSAY,
    cascade_splits=CASCADE_SPLITS,
) -> dict[str, dict[str, np.ndarray]]:
    """Calculate natural-uranium feed, tails, and SWU from fuel receipts.

    Parameters
    ----------
    receipts : iterable of FuelReceipt
        Individual fuel receipts from either simulator.
    reactors : sequence of str
        Reactor names that may appear in ``receipts``.
    n_times : int
        Number of points on the result time axis.
    natu_assay : float
        U-235 assay of the natural-uranium feed, expressed as a fraction.
    tails_assay : float
        U-235 assay of the final tails, expressed as a fraction.
    cascade_splits : sequence of float or None, optional
        Upper product-assay limits for the enrichment stages.  ``None`` uses
        the WATTS defaults ``[0.1, 0.2]``.

    Returns
    -------
    dict of str to dict of str to numpy.ndarray
        Natural-uranium feed, tails, and SWU arrays grouped by reactor.  Tails
        and SWU have shape ``(stages, n_times)``; natural uranium has shape
        ``(n_times,)``.

    Raises
    ------
    ValueError
        If assays, stage limits, time positions, masses, reactor names, or
        returned cascade shapes are invalid.

    Notes
    -----
    Each receipt is calculated separately because SWU and feed requirements
    are nonlinear in product assay.  The plugin combines these results only
    after the calculation.
    """

    # Report missing scientific inputs by name before converting them.  This
    # gives a useful message instead of a later numeric conversion error.
    if natu_assay is None:
        raise ValueError("natu_assay is required and must be numeric.")
    if tails_assay is None:
        raise ValueError("tails_assay is required and must be numeric.")

    # Both plugins pass through this check, so they report the same error for
    # nonnumeric assay values.
    try:
        natu_assay = float(natu_assay)
        tails_assay = float(tails_assay)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "natu_assay and tails_assay must both be numeric values."
        ) from exc

    if not 0.0 < natu_assay < 1.0:
        raise ValueError("natu_assay must be strictly between zero and one.")
    if not 0.0 < tails_assay < natu_assay:
        raise ValueError("tails_assay must satisfy 0 < tails < natural assay.")

    # A fractional time count would silently remove part of the result axis if
    # converted to an integer, so require an exact non-negative integer.
    try:
        time_count = int(n_times)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("n_times must be a non-negative integer.") from exc
    if time_count < 0 or time_count != n_times:
        raise ValueError("n_times must be a non-negative integer.")
    n_times = time_count

    reactor_names = tuple(dict.fromkeys(str(name) for name in reactors))
    splits = _check_cascade_splits(cascade_splits, natu_assay)
    # The helper pads multi-stage results to len(splits) + 1.  A single
    # infinity split is the special one-stage request.
    n_stages = 1 if splits == [np.inf] else len(splits) + 1

    result = {
        "natu": {name: np.zeros(n_times) for name in reactor_names},
        "tails": {
            name: np.zeros((n_stages, n_times)) for name in reactor_names
        },
        "swu": {
            name: np.zeros((n_stages, n_times)) for name in reactor_names
        },
    }
    cascade_cache = {}

    for receipt in receipts:
        if receipt.reactor not in result["natu"]:
            raise ValueError(
                f"Fuel receipt references unknown reactor "
                f"{receipt.reactor!r}."
            )
        try:
            time_index = int(receipt.time_index)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                f"Fuel receipt has a noninteger time index: {receipt!r}."
            ) from exc
        if time_index != receipt.time_index:
            raise ValueError(
                f"Fuel receipt has a noninteger time index: {receipt!r}."
            )
        if not 0 <= time_index < n_times:
            raise ValueError(
                f"Fuel receipt time index {receipt.time_index} is outside "
                f"the analysis axis of length {n_times}."
            )

        material_mass = float(receipt.material_mass)
        uranium_mass = float(receipt.uranium_mass)
        u235_mass = float(receipt.u235_mass)
        if not all(np.isfinite(v) for v in (material_mass, uranium_mass, u235_mass)):
            raise ValueError(f"Fuel receipt contains non-finite mass: {receipt!r}.")
        if material_mass < 0 or uranium_mass < 0 or u235_mass < 0:
            raise ValueError(f"Fuel receipt masses cannot be negative: {receipt!r}.")
        if uranium_mass > material_mass and not np.isclose(
            uranium_mass,
            material_mass,
            rtol=1.0e-12,
            atol=1.0e-12,
        ):
            raise ValueError("Uranium mass cannot exceed total material mass.")
        if u235_mass > uranium_mass and not np.isclose(
            u235_mass,
            uranium_mass,
            rtol=1.0e-12,
            atol=1.0e-12,
        ):
            raise ValueError("U-235 mass cannot exceed uranium mass.")

        # Non-uranium fuel contributes no uranium enrichment requirement.  It
        # remains valid receipt data and is not treated as malformed.
        if uranium_mass == 0.0:
            continue

        product_assay = u235_mass / uranium_mass
        if not 0.0 <= product_assay < 1.0:
            raise ValueError(
                f"Product assay must be in [0, 1), got {product_assay:.12g}."
            )

        reactor = receipt.reactor
        if product_assay < natu_assay and not np.isclose(
            product_assay, natu_assay
        ):
            # Depleted/recycled uranium is not the product of this
            # natural-feed enrichment cascade.  It therefore contributes no
            # new natural feed, enrichment tails, or separative work.  The
            # receipt remains part of fuel demand and fabrication in the rest
            continue
        if np.isclose(product_assay, natu_assay):
            # Natural-uranium fuel needs one kg of natural feed per kg of
            # uranium product and performs no separative work.
            result["natu"][reactor][time_index] += uranium_mass
            continue

        cache_key = round(product_assay, 12)
        if cache_key not in cascade_cache:
            cascade = enrichment_cascade(
                feed_enr=natu_assay,
                prod_enr=float(product_assay),
                tail_enr=tails_assay,
                cascade_splits=splits,
            )
            tails = np.asarray(cascade["tails"], dtype=float)
            swu = np.asarray(cascade["swu"], dtype=float)
            if tails.ndim != 1 or swu.ndim != 1:
                raise ValueError(
                    "Enrichment cascade returned an inconsistent stage shape: "
                    f"tails={tails.shape}, swu={swu.shape}, expected "
                    f"{(n_stages,)}."
                )
            if len(tails) > n_stages or len(swu) > n_stages:
                raise ValueError(
                    "Enrichment cascade returned more stages than requested: "
                    f"tails={tails.shape}, swu={swu.shape}, maximum "
                    f"{(n_stages,)}."
                )
            # The enrichment function returns only the stages needed for this
            # assay.  Add zero rows for unused higher stages so every reactor
            # has the same result shape.
            tails = np.pad(tails, (0, n_stages - len(tails)))
            swu = np.pad(swu, (0, n_stages - len(swu)))
            cascade_cache[cache_key] = (
                float(cascade["feed"][0]),
                tails,
                swu,
            )

        feed_ratio, tails_ratio, swu_ratio = cascade_cache[cache_key]
        # Ratios are per unit *uranium product*.  Multiplication by total
        # material mass would over-count oxygen, plutonium, cladding, or other
        # constituents in a fuel resource.
        result["natu"][reactor][time_index] += feed_ratio * uranium_mass
        result["tails"][reactor][:, time_index] += tails_ratio * uranium_mass
        result["swu"][reactor][:, time_index] += swu_ratio * uranium_mass

    return result


def format_fuel_resource_results(
    resources: Mapping[str, Mapping[str, np.ndarray]],
    reactors: Sequence[str],
    n_times: int,
    return_sum: bool,
    split_categories: bool,
):
    """Prepare shared fuel-resource arrays for a public plugin result.

    Parameters
    ----------
    resources : mapping
        Shared fuel-resource data arranged as
        ``metric -> reactor -> array``.
    reactors : sequence of str
        Reactors to include in the returned result.
    n_times : int
        Required number of points on the result time axis.
    return_sum : bool
        Return one array per metric when ``True``; otherwise return one array
        per reactor and metric.
    split_categories : bool
        Keep separate enrichment-stage rows for tails and SWU when ``True``.

    Returns
    -------
    dict
        Dictionary with ``"natu"``, ``"tails"``, and ``"swu"`` results in
        the requested summed or per-reactor form.

    Raises
    ------
    ValueError
        If a required metric or reactor is missing, or if array shapes do not
        agree with ``n_times`` and the common stage count.
    """

    reactor_names = tuple(reactors)
    missing_metrics = [
        metric for metric in ("natu", "tails", "swu")
        if metric not in resources
    ]
    if missing_metrics:
        raise ValueError(
            f"Fuel resources are missing metric(s): {missing_metrics}."
        )

    formatted = {}
    stage_count = None
    for metric in ("natu", "tails", "swu"):
        per_reactor = {}
        for reactor in reactor_names:
            if reactor not in resources[metric]:
                raise ValueError(
                    f"Fuel resource metric {metric!r} has no data for "
                    f"reactor {reactor!r}."
                )
            values = np.asarray(resources[metric][reactor], dtype=float)
            if metric == "natu":
                if values.shape != (n_times,):
                    raise ValueError(
                        f"Natural-uranium data for {reactor!r} has shape "
                        f"{values.shape}; expected {(n_times,)}."
                    )
            else:
                if values.ndim != 2 or values.shape[1] != n_times:
                    raise ValueError(
                        f"{metric.upper()} data for {reactor!r} has shape "
                        f"{values.shape}; expected (stages, {n_times})."
                    )
                if stage_count is None:
                    stage_count = values.shape[0]
                elif values.shape[0] != stage_count:
                    raise ValueError(
                        "Tails and SWU must use one consistent enrichment-"
                        f"stage count; got {values.shape[0]} and "
                        f"{stage_count}."
                    )

            if metric != "natu" and not split_categories:
                values = values.sum(axis=0)
            per_reactor[reactor] = np.array(values, copy=True)

        if not return_sum:
            formatted[metric] = per_reactor
            continue

        if not per_reactor:
            # No selected reactor provides a stage count.  Return an empty
            # stage axis for split tails and SWU, and a zero time series for
            # all one-dimensional results.
            if metric != "natu" and split_categories:
                formatted[metric] = np.zeros((0, n_times))
            else:
                formatted[metric] = np.zeros(n_times)
        else:
            formatted[metric] = np.sum(
                np.stack(list(per_reactor.values()), axis=0), axis=0
            )
    return formatted


class ResultFileReader:
    """Open simulator result files only when their data are requested.

    ``Plugin.__call__`` constructs a Results object in a temporary directory,
    moves its files into the WATTS database, and then saves the Results
    metadata.  Opening SQLite or HDF5 during construction would use the old
    path.  An open SQLite connection also cannot be saved.  This base class
    waits until ``result.obj`` is requested, then opens the file at its current
    path.

    Notes
    -----
    A simulator-specific result class supplies ``_result_file_path`` and
    ``_open_result_file``.
    """

    def _initialize_result_reader(self):
        """Set the initial closed state for the result-file reader.

        Returns
        -------
        None
            This method updates the reader state in place.
        """

        self._reader = None
        self._reader_path = None

    def _result_file_path(self) -> Path:
        """Return the current simulator output path.

        Returns
        -------
        pathlib.Path
            Path used to open the simulator-specific reader.
        """

        raise NotImplementedError

    def _open_result_file(self, path: Path):
        """Open the simulator-specific reader for one output file.

        Parameters
        ----------
        path : pathlib.Path
            Simulator output file to open.

        Returns
        -------
        object
            Cyclus or DYMOND output reader.
        """

        raise NotImplementedError

    @property
    def obj(self):
        """Return the reader for the result file at its current path.

        Returns
        -------
        object
            Open Cyclus or DYMOND output reader.
        """

        current_path = Path(self._result_file_path()).resolve()
        # Reopen the reader if WATTS or the caller moved the result file after
        # it was first opened.
        if self._reader is not None and self._reader_path != current_path:
            self.close_result_file()
        if self._reader is None:
            self._reader = self._open_result_file(current_path)
            self._reader_path = current_path
        return self._reader

    def get_object(self):
        """Return the reader for the simulator output file.

        Returns
        -------
        object
            Open Cyclus or DYMOND output reader, as returned by :attr:`obj`.
        """

        return self.obj

    def close_result_file(self):
        """Close the current simulator output reader.

        Returns
        -------
        None
            This method closes the reader in place.  Calling it when no file
            is open is safe.
        """

        if self._reader is not None:
            close = getattr(self._reader, "close", None)
            if close is not None:
                close()
        self._reader = None
        self._reader_path = None

    def move_files(self, dst):
        """Close the reader before moving the result files.

        Parameters
        ----------
        dst : str or pathlib.Path
            Directory that will receive the result files.

        Returns
        -------
        None
            The files and stored paths are updated in place.

        Notes
        -----
        SQLite may lock an open file on Windows.  Closing the reader before
        the move keeps the normal WATTS workflow and interactive use reliable.
        """

        self.close_result_file()
        # Results.move_files performs the actual move and updates every stored
        # input and output path.
        return super().move_files(dst)

    def __getstate__(self):
        """Return result data that WATTS can save safely.

        Returns
        -------
        dict
            Instance data with the open reader and its path removed.
        """

        state = self.__dict__.copy()
        # File readers may hold open connections or large data arrays.  WATTS
        # stores only the paths and opens a new reader when data are requested.
        state["_reader"] = None
        state["_reader_path"] = None
        return state

    def __setstate__(self, state):
        """Restore saved result data with the output reader closed.

        Parameters
        ----------
        state : dict
            Saved instance data produced by :meth:`__getstate__`.

        Returns
        -------
        None
            The instance data are restored in place.
        """

        self.__dict__.update(state)
        self._reader = None
        self._reader_path = None
