import numpy as np
import numbers


def feed_to_product_ratio(
    feed_enr: float | list[float],
    prod_enr: float | list[float],
    tail_enr: float | list[float],
) -> float:
    """
    Calculate the feed-to-product ratio for a given enrichment process.

    Parameters
    ----------
    feed_enr : float or list of float
        Enrichment of the feed material.
    prod_enr : float or list of float
        Enrichment of the product material.
    tail_enr : float or list of float
        Enrichment of the tails material.

    Returns
    -------
    float or list of float
        Feed-to-product ratio for the given enrichment process.
    """
    # Convert inputs to numpy arrays
    feed_enr = np.atleast_1d(feed_enr)
    prod_enr = np.atleast_1d(prod_enr)
    tail_enr = np.atleast_1d(tail_enr)

    # Calculate the feed-to-product ratio, based on product, feed,
    # and tails enrichments
    ratio = (prod_enr - tail_enr) / (feed_enr - tail_enr)
    ratio[prod_enr == 0] = 0  # Set ratio to 0 if product enrichment is 0
    assert np.all(
        ratio >= 0
    ), (f"Feed-to-product ratio cannot be negative.\nRatio: {ratio}.\n"
        f"Input was:\n"
        f"\tFeed: {feed_enr}\tProduct: {prod_enr}\n\tTails: {tail_enr}")
    return ratio.item() if ratio.size == 1 else ratio


def tails_to_product_ratio(
    feed_enr: float | list[float],
    prod_enr: float | list[float],
    tail_enr: float | list[float],
) -> float:
    """
    Calculate the tails-to-product ratio for a given enrichment process.

    Parameters
    ----------
    feed_enr : float or list of float
        Enrichment of the feed material.
    prod_enr : float or list of float
        Enrichment of the product material.
    tail_enr : float or list of float
        Enrichment of the tails material.

    Returns
    -------
    float or list of float
        Tails-to-product ratio for the given enrichment process.
    """
    # Convert inputs to numpy arrays
    feed_enr = np.atleast_1d(feed_enr)
    prod_enr = np.atleast_1d(prod_enr)
    tail_enr = np.atleast_1d(tail_enr)

    # Calculate the tails-to-product ratio based on product, feed,
    # and tails enrichments
    ratio = (prod_enr - feed_enr) / (feed_enr - tail_enr)
    ratio[prod_enr == 0] = 0  # Set ratio to 0 if product enrichment is 0
    assert np.all(
        ratio >= 0
    ), (f"Tails-to-product ratio cannot be negative.\nRatio: {ratio}.\n"
        f"Input was:\n"
        f"\tFeed: {feed_enr}\n\tProduct: {prod_enr}\n\tTails: {tail_enr}")
    return ratio.item() if ratio.size == 1 else ratio


def _value_function(enr: float | list[float]):
    """
    Helper function to calculate the separative work unit (SWU) for a 
    given enrichment level.
    This function is used internally by the calculate_swu method.

    Parameters
    ----------
    enr : float or list of float
        Enrichment level of the material, expressed as a decimal (0 to 1).

    Returns
    -------
    float or list of float
        SWU value for the given enrichment level.
    """
    # Convert inputs to numpy arrays
    enr = np.atleast_1d(enr)
    result = np.zeros_like(enr)

    # Mask for valid enrichment values (0 < enr < 1). The rest will be 0.
    mask = (enr > 0) & (enr < 1)

    # Formula is: f(x) = (2x - 1) * log(x / (1 - x)) where x is the enrichment
    result[mask] = (2 * enr[mask] - 1) * np.log(enr[mask] / (1 - enr[mask]))
    return result if result.shape else result.item()


def swu_to_product_ratio(
    feed_enr: float | list[float],
    prod_enr: float | list[float],
    tail_enr: float | list[float],
) -> float | np.ndarray:
    """
    Calculate the separative work unit (SWU) to product ratio 
    for a given enrichment process.

    Parameters
    ----------
    feed_enr : float or list of float
        Enrichment of the feed material.
    prod_enr : float or list of float
        Enrichment of the product material.
    tail_enr : float or list of float
        Enrichment of the tails material.

    Returns
    -------
    float or np.ndarray
        SWU-to-product ratio for the given enrichment process.
    """

    # Convert to arrays
    feed_enr = np.atleast_1d(feed_enr)
    prod_enr = np.atleast_1d(prod_enr)
    tail_enr = np.atleast_1d(tail_enr)

    # Compute intermediate ratios
    tails_ratio = tails_to_product_ratio(feed_enr, prod_enr, tail_enr)
    feed_ratio = feed_to_product_ratio(feed_enr, prod_enr, tail_enr)

    # Compute value terms
    Vp = _value_function(prod_enr)
    Vf = _value_function(feed_enr)
    Vt = _value_function(tail_enr)

    # Final SWU per product formula
    ratio = Vp + tails_ratio * Vt - feed_ratio * Vf
    ratio[prod_enr == 0] = 0  # Set SWU to 0 if product enrichment is 0
    assert np.all(
        ratio >= 0
    ), (f"SWU-to-product ratio cannot be negative.\nRatio: {ratio}.\n"
        f"Input was:\n"
        f"\tFeed: {feed_enr}\n\tProduct: {prod_enr}\n\tTails: {tail_enr}")
    return ratio.item() if ratio.size == 1 else ratio


def enrichment_cascade(
    feed_enr, prod_enr, tail_enr, cascade_splits=[0.1, 0.2], printing=False
):
    """
    Calculate the SWU, feed, and tail distributions across different 
    stages of enrichment.
    By cascade, it is understood that the tails of the next stage is
    the feed for the previous stage.

    Parameters:
    -----------
    feed_enr: float, optional
        Feed enrichment level, expressed as a decimal
        (default is 0.00711)
    prod_enr: float
        Final product enrichment level, expressed as a decimal
    tail_enr: float
        Tailing enrichment level, expressed as a decimal
    cascade_splits: list of float, optional
        Enrichment levels at intermediate stages (default is
        [0.1, 0.2], corresponding to CAT-III, II, I)
    printing: bool
        for debugging.

    Returns:
    --------
    Dictionary
        Dictionary containing lists of SWU, feed, and tails
        quantities for each stage of the enrichment process.
    """
    # make sure these are numbers
    enr_inputs_dict = {
        "feed": feed_enr,
        "prod": prod_enr,
        "tail": tail_enr
    }
    for variable, val in enr_inputs_dict.items():
        assert isinstance(
            val, numbers.Number), \
        f"Variable {variable} needs to be a single number."

    # edge case of just one
    if cascade_splits is None:
        cascade_splits = [np.inf]

    if len(cascade_splits) == 1 and cascade_splits[0] > prod_enr:
        # just one shot
        cascade_data = {
            'swu': [swu_to_product_ratio(feed_enr, prod_enr, tail_enr)],
            'feed': [feed_to_product_ratio(feed_enr, prod_enr, tail_enr)],
            'tails': [tails_to_product_ratio(feed_enr, prod_enr, tail_enr)]
        }
        return cascade_data

    # Add product enrichments list:
    stage_product_enrichments = []
    cascade_splits = np.array(list(cascade_splits))
    for enr in cascade_splits:
        if prod_enr > enr:
            stage_product_enrichments.append(enr)
    stage_product_enrichments.append(prod_enr)

    # Add feed enrichments
    stage_feed_enrichments = [feed_enr] + stage_product_enrichments[:-1]

    # Repeat tails enrichment for each stage if only one value is provided
    stage_tail_enrichments = [tail_enr]
    if len(cascade_splits) > 1:
        stage_tail_enrichments.append(feed_enr)
    if len(cascade_splits) > 2:
        stage_tail_enrichments.extend(cascade_splits[:-2])

    if len(cascade_splits) == len(stage_product_enrichments):
        # using all the stages
        assert (
            len(cascade_splits)
            == len(stage_feed_enrichments)
            == len(stage_product_enrichments)
            == len(stage_tail_enrichments)
        )
    else:  # not using all the stages
        assert len(stage_product_enrichments) == len(stage_feed_enrichments)
        # cut off unnecessary stages
        stage_tail_enrichments = stage_tail_enrichments[
            : len(stage_product_enrichments)
        ]

    # Calculate values
    multistage_dict = multistage_enr(
        stage_feed_enrichments,
        stage_product_enrichments,
        stage_tail_enrichments,
        printing=printing,
    )
    cascade_data = {}
    for key in multistage_dict:
        cascade_data[key] = list(multistage_dict[key])
        while (
            len(cascade_data[key]) < len(cascade_splits) + 1
        ):  # Add zeros for higher enrichment categories
            cascade_data[key].append(0)

    # Verify the total SWU calculated matches the total expected 
    # from feed to product if tails are uniform
    if len(np.unique(stage_tail_enrichments)) == 1:
        stage_swus = cascade_data["swu"]
        total_swu = swu_to_product_ratio(feed_enr, prod_enr, tail_enr)
        if not np.isclose(sum(stage_swus), total_swu):
            raise ValueError(
                "Calculated total SWU does not match the expected total SWU."
            )

    return cascade_data


def multistage_enr(feed_enrs, prod_enrs, tails_enrs, printing=True):
    """
    Calculate the SWU, feed, and tails quantities for each stage
    of a multi-stage enrichment process.

    Parameters:
    -----------
    feed_enrs : list of float
        List of enrichment levels for the feed material at each stage.
    prod_enrs : list of float
        List of enrichment levels for the product material at each stage.
    tails_enrs : list of float
        List of enrichment levels for the tails material at each stage.
    printing : bool, optional
        Whether to print the details of each stage (default is True).

    Returns:
    --------
    dict
        Dictionary containing lists of SWU, feed, and tails quantities
        for each stage.
    """
    if printing:
        print("Calculating SWU for multi-stage enrichment process:")
        print("\tFeed Enrichments:", feed_enrs)
        print("\tProduct Enrichments:", prod_enrs)
        print("\tTailing Enrichments:", tails_enrs)

    # Ensure lists, not arrays
    feed_enrs = [feed_enrs] if np.isscalar(feed_enrs) else list(feed_enrs)
    tails_enrs = [tails_enrs] if np.isscalar(
        tails_enrs) else list(tails_enrs)

    if np.isscalar(prod_enrs):
        if len(feed_enrs) > 1:
            prod_enrs = feed_enrs[1:] + [prod_enrs]
        else:
            prod_enrs = [prod_enrs]
    else:
        prod_enrs = list(prod_enrs)

    # Trim feed and tails if product levels do not require all stages
    if len(prod_enrs) < len(feed_enrs):
        final_enr = prod_enrs[-1]
        for indx, val in enumerate(feed_enrs):
            if val > final_enr:
                break
        feed_enrs = feed_enrs[:indx]
        tails_enrs = tails_enrs[:indx]

    assert (
        len(feed_enrs) == len(prod_enrs) == len(tails_enrs)
    ), (f"Mismatch in number of stages: "
        f"feed={len(feed_enrs)}, prod={len(prod_enrs)}, tail={len(tails_enrs)}")
    assert (
        prod_enrs[0] > feed_enrs[0] > tails_enrs[0]
    ), (f"Stage 0 must satisfy prod > feed > tails: "
        f"prod={prod_enrs[0]}, feed={feed_enrs[0]}, tail={tails_enrs[0]}")

    n_stages = len(feed_enrs)

    # Check that each product enrichments matches the feed of next stage
    for n in range(n_stages - 1):
        assert (
            prod_enrs[n] == feed_enrs[n + 1]
        ), (f"Stage {n}: product enrichment {prod_enrs[n]} "
            f"does not match next stage feed {feed_enrs[n+1]}.")

    # Verify consistent tail values unless reused as feed
    for indx, val in enumerate(tails_enrs):
        if indx == 0:
            continue
        if val != tails_enrs[0] and val not in feed_enrs[:indx]:
            raise ValueError("Tailing is not consistent or reused as feed.")

    # Backward pass to compute required flows
    swu_list = [0.0] * n_stages
    feed_list = [0.0] * n_stages
    tails_list = [0.0] * n_stages
    qty_prod = [0.0] * n_stages
    qty_prod[-1] = 1.0  # target is unit product

    for n in range(n_stages - 1, -1, -1):
        swu = qty_prod[n] * swu_to_product_ratio(
            feed_enrs[n], prod_enrs[n], tails_enrs[n]
        )
        feed = qty_prod[n] * feed_to_product_ratio(
            feed_enrs[n], prod_enrs[n], tails_enrs[n]
        )
        qty_tails = feed - qty_prod[n]

        matches = np.isclose(feed_enrs, tails_enrs[n], atol=1e-8)
        if np.any(matches):
            indx = np.where(matches)[0][0]
            feed_list[indx] -= qty_tails
            if indx != 0:
                qty_prod[indx - 1] -= qty_tails
        else:
            tails_list[n] += qty_tails

        if printing:
            print(f"\tStage {n}:")
            print(
                f"\t\tProd qty: {qty_prod[n]:.6f} (enr: {prod_enrs[n]: .4%})")
            print(f"\t\tFeed qty: {feed:.6f} (enr: {feed_enrs[n]: .4%})")
            print(
                f"\t\tTails qty: {qty_tails:.6f} (enr: {tails_enrs[n]: .4%})")
            if np.any(matches):
                print(f"\t\tSubtracting {qty_tails:.6f} from stage {indx}")

        if n != 0:
            qty_prod[n - 1] += feed
        swu_list[n] += swu
        feed_list[n] += feed

    return {"swu": swu_list, "feed": feed_list, "tails": tails_list}
