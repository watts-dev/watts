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
        Enrichment of the feed material as a decimal.
    prod_enr : float or list of float
        Enrichment of the product material as a decimal.
    tail_enr : float or list of float
        Enrichment of the tails material as a decimal.

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
    # If every product-enrichment entry is zero, the ratio is zero
    if np.all(prod_enr == 0):
        return 0 if np.isscalar(prod_enr) else np.zeros_like(prod_enr)

    # Otherwise, compute the ratio
    ratio = (prod_enr - tail_enr) / (feed_enr - tail_enr)

    # Catch negative ratios early and raise a helpful error
    if np.any(np.atleast_1d(ratio) < 0):
        raise ValueError(
            "Feed-to-product ratio cannot be negative.\n"
            f"Computed ratio: {ratio}\nInput values:\n"
            f"\tFeed: {feed_enr}\n\tProduct: {prod_enr}\n\tTails: {tail_enr}"
        )
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
        Enrichment of the feed material as a decimal.
    prod_enr : float or list of float
        Enrichment of the product material as a decimal.
    tail_enr : float or list of float
        Enrichment of the tails material as a decimal.

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
    # If every product-enrichment entry is zero, the ratio is zero
    if np.all(prod_enr == 0):
        return 0 if np.isscalar(prod_enr) else np.zeros_like(prod_enr)

    # Otherwise, compute the ratio
    ratio = (prod_enr - feed_enr) / (feed_enr - tail_enr)

    # Catch negative ratios early and raise a helpful error
    if np.any(np.atleast_1d(ratio) < 0):
        raise ValueError(
            "Tails-to-product ratio cannot be negative.\n"
            f"Computed ratio: {ratio}\nInput values:\n"
            f"\tFeed: {feed_enr}\n\tProduct: {prod_enr}\n\tTails: {tail_enr}"
        )
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
        Enrichment of the feed material as a decimal.
    prod_enr : float or list of float
        Enrichment of the product material as a decimal.
    tail_enr : float or list of float
        Enrichment of the tails material as a decimal.

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

    # If every product-enrichment entry is zero, the ratio is zero
    if np.all(prod_enr == 0):
        return 0 if np.isscalar(prod_enr) else np.zeros_like(prod_enr)

    # Otherwise, compute the ratio
    # Compute value terms
    Vp = _value_function(prod_enr)
    Vf = _value_function(feed_enr)
    Vt = _value_function(tail_enr)
    # Final SWU per product formula
    ratio = Vp + tails_ratio * Vt - feed_ratio * Vf
    ratio[prod_enr == 0] = 0  # Set SWU to 0 if product enrichment is 0

    # Catch negative ratios early and raise a helpful error
    if np.any(np.atleast_1d(ratio) < 0):
        raise ValueError(
            "SWU-to-product ratio cannot be negative.\n"
            f"Computed ratio: {ratio}\nInput values:\n"
            f"\tFeed: {feed_enr}\n\tProduct: {prod_enr}\n\tTails: {tail_enr}"
        )
    return ratio.item() if ratio.size == 1 else ratio


def enrichment_cascade(
    feed_enr, prod_enr, tail_enr,
    cascade_splits=(0.1, 0.2), printing=False
):
    """Calculate feed, tails, and SWU for an enrichment cascade.

    In a multistage cascade, the feed to each higher-assay stage comes from
    the product of the preceding stage.  Material rejected by a higher stage
    returns to the feed assay of the preceding stage.

    Parameters
    ----------
    feed_enr : float
        U-235 assay of the initial feed, expressed as a fraction.
    prod_enr : float
        U-235 assay of the final product, expressed as a fraction.
    tail_enr : float
        U-235 assay of the final tails, expressed as a fraction.
    cascade_splits : sequence of float or None, optional
        Product-assay limits between stages.  The default ``(0.1, 0.2)``
        represents the boundaries between enrichment categories III, II,
        and I.  ``None`` requests one stage without a finite assay limit.
    printing : bool, optional
        Print the values calculated for each stage when ``True``.

    Returns
    -------
    dict of str to list of float
        Per-stage ratios for ``"swu"``, ``"feed"``, and ``"tails"``.  Each
        value is reported per unit of final product mass.

    Raises
    ------
    AssertionError
        If an assay input is not a single number or the stage data do not have
        matching lengths.
    ValueError
        If the assays cannot define a physical enrichment calculation or the
        calculated stage SWU does not agree with the full-cascade SWU.
    """
    # Each assay must be one number because one call describes one product.
    enr_inputs_dict = {
        "feed": feed_enr,
        "prod": prod_enr,
        "tail": tail_enr
    }
    for variable, enrichment in enr_inputs_dict.items():
        assert isinstance(
            enrichment, numbers.Number), \
            f"Variable {variable} needs to be a single number."

    # The enrichment functions use infinity to represent one stage with no
    # intermediate product-assay limit.
    if cascade_splits is None:
        cascade_splits = [np.inf]

    if len(cascade_splits) == 1 and cascade_splits[0] > prod_enr:
        # No stage boundary lies below the requested product assay, so a
        # standard single-stage calculation is sufficient.
        cascade_data = {
            'swu': [swu_to_product_ratio(feed_enr, prod_enr, tail_enr)],
            'feed': [feed_to_product_ratio(feed_enr, prod_enr, tail_enr)],
            'tails': [tails_to_product_ratio(feed_enr, prod_enr, tail_enr)]
        }
        return cascade_data

    # Include only stage limits below the final product assay, followed by the
    # requested final assay itself.
    stage_product_enrichments = []
    cascade_splits = np.array(list(cascade_splits))
    for enrichment in cascade_splits:
        if prod_enr > enrichment:
            stage_product_enrichments.append(enrichment)
    stage_product_enrichments.append(prod_enr)

    # The product from one stage becomes the feed to the next stage.
    stage_feed_enrichments = [feed_enr] + stage_product_enrichments[:-1]

    # The first stage discards to the requested final tails assay.  Every later
    # stage cascades down into the preceding feed: natural feed for stage one,
    # then each lower split in turn.  Build enough candidates for the maximum
    # possible number of stages and trim them to the splits actually below the
    # requested product assay.  This works uniformly for one finite split,
    # products between splits, and products above every configured split.
    stage_tail_candidates = (
        [tail_enr, feed_enr] + list(cascade_splits[:-1])
    )
    stage_tail_enrichments = stage_tail_candidates[
        : len(stage_product_enrichments)
    ]

    # Each list describes the same physical stages.  Check their lengths here
    # so an error is reported before the stage calculations begin.
    assert (
        len(stage_feed_enrichments)
        == len(stage_product_enrichments)
        == len(stage_tail_enrichments)
    )

    # Calculate all stages together because material from a higher stage feeds
    # back into the preceding stage.
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
        List of enrichment levels for the feed material at each stage as 
        decimals.
    prod_enrs : list of float
        List of enrichment levels for the product material at each stage 
        as decimals.
    tails_enrs : list of float
        List of enrichment levels for the tails material at each stage
        as decimals.
    printing : bool, optional
        Whether to print the details of each stage (default is True).

    Returns:
    --------
    dict
        Dictionary containing lists of SWU, feed, and tails quantities
        for each stage, in units of kg.
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
