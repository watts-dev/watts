import numpy as np
import copy

def calculate_feed(e_feed, e_tail, e_prod):
    '''
    Calculate the ratio of of the feed:product material. This 
    value should then be multiplied by the product mass to obtain 
    the actual feed material mass

    Parameters:
    -----------
    e_feed: float
        enrichment level of the feed material, expressed as a decimal
    e_tail: float
        enrichment level of the tails material, expressed as a decimal
    e_prod: float
        enrichment level of the product material, expressed as a decimal
    
    Returns:
    --------
    ratio of feed:product material
    '''
    return (e_prod - e_tail)/(e_feed - e_tail)


def calculate_tails(e_feed, e_tail, e_prod):
    """
    Calculate the ratio of tails:product material. This 
    value should then be multiplied by the product mass to obtain 
    the actual tails material mass

    Parameters:
    -----------
    e_feed: float
        Enrichment level of the feed material, expressed as a decimal
    e_tail: float
        Enrichment level of the tails material, expressed as a decimal
    e_prod: float
        Enrichment level of the product material, expressed as a decimal
    
    Returns:
    --------
    ratio of tails:product material
    """
    return (e_prod - e_feed) / (e_feed - e_tail)

def calculate_swu(e_feed, e_tail, e_prod):
    '''
    Calculate the swu/kg of product material. This value should be 
    multiplied by the product material mass to get the swu capacity. 

    Parameters:
    -----------
    e_feed: float
        enrichment level of the feed material, expressed as a decimal
    e_tail: float
        enrichment level of the tails material, expressed as a decimal
    e_prod: float
        enrichment level of the product material, expressed as a decimal
    
    Returns:
    --------
    swu capacity per unit mass of product material
    '''
    f = calculate_feed(e_feed, e_tail, e_prod)
    p = 1
    t = f - p

    return p * v(e_prod) + t * v(e_tail) - f * v(e_feed)


def v(x: float):
    if x <= 0 or x >= 1:
        return 0.0
    return (2*x - 1) * np.log(x / (1 - x))



def calculate_swu_split_cats(e_feed:float, e_tail:float, e_prod:float):
    '''
    Parameters:
    -----------
    e_feed: float
        enrichment level of the feed material, expressed as a decimal
    e_tail: float
        enrichment level of the tails material, expressed as a decimal
    e_prod: float
        enrichment level of the product material, expressed as a decimal

    Returns:
    --------
    swus: array of size (3,)
       SWU capacity/unit mass of product for each category, in 
       increasing order of category level requirements 
       ([0] is Cat3, [1] is Cat2, [2] is Cat 1). Category 
       1 calculations are not currently supported.
    '''
    swus = np.zeros(3)
    assert(e_prod < 0.2), 'Not gonna do cat1 yet.'
    if e_prod > 0.1:
        cat3_swu = calculate_swu(e_feed, e_tail, 0.1)
        cat2_swu = calculate_swu(0.1, e_tail, e_prod)
        
        cat2_feed = calculate_feed(0.1, e_tail, e_prod)
        swus[0] = cat3_swu * cat2_feed
        swus[1] = cat2_swu

        # sanity check
        tot_swu = calculate_swu(e_feed, e_tail, e_prod)
        assert(np.isclose(sum(swus), tot_swu))
    else:
        swus[0] = calculate_swu(e_feed, e_tail, e_prod)

    return swus


def calculate_swu_split(prod_enr, tailing_enr, feed_enr=0.00711, cascade_splits=[0.1,0.2], printing=False):
    '''
    Calculate the SWU distribution across different stages of enrichment.

    Parameters:
    -----------
    prod_enr: float
        Final product enrichment level, expressed as a decimal
    tailing_enr: float
        Tailing enrichment level, expressed as a decimal
    feed_enr: float, optional
        Feed enrichment level, expressed as a decimal 
        (default is 0.00711)
    cascade_splits: list of float, optional
        Enrichment levels at intermediate stages (default is 
        [0.1, 0.2], corresponding to CAT-III, II, I)

    Returns:
    --------
    List of SWU values for each stage of enrichment
    '''
    # Add product enrichments list: 
    stage_product_enrichments = []
    cascade_splits = np.array(list(cascade_splits))
    for enr in cascade_splits:
        if prod_enr > enr:
            stage_product_enrichments.append(enr)
    stage_product_enrichments.append(prod_enr)
    
    # Add feed enrichments
    if type(feed_enr) in [float, int]:
        stage_feed_enrichments = [feed_enr] + stage_product_enrichments[:-1]
    else:
        stage_feed_enrichments = feed_enr
    
    # Repeat tails enrichment for each stage if only one value is provided
    stage_tail_enrichments = np.atleast_1d(tailing_enr)
    if len(stage_tail_enrichments) == 1:
        stage_tail_enrichments = np.full_like(stage_product_enrichments, stage_tail_enrichments[0])

    # Calculate values
    multistage_dict = multistage_enr(stage_feed_enrichments, stage_product_enrichments, stage_tail_enrichments, printing=printing)
    stage_swus = multistage_dict['swu']
    while len(stage_swus) < len(cascade_splits)+1: # Add zeros for higher enrichment categories
        stage_swus.append(0)
    
    # Verify the total SWU calculated matches the total expected from feed to product if tails are uniform
    if len(np.unique(stage_tail_enrichments)) == 1:
        total_swu = calculate_swu(feed_enr, tailing_enr, prod_enr)
        if not np.isclose(sum(stage_swus), total_swu):
            raise ValueError("Calculated total SWU does not match the expected total SWU.")

    return stage_swus


def multistage_enr(feed_enrs, prod_enrs, tailing_enrs, printing=True):
    '''
    Calculate the SWU, feed, and tailing quantities for each stage 
    of a multi-stage enrichment process.

    Parameters:
    -----------
    feed_enrs: list of float
        List of enrichment levels for the feed material at each stage
    prod_enrs: list of float
        List of enrichment levels for the product material at each stage
    tailing_enrs: list of float
        List of enrichment levels for the tails material at each stage
    printing: bool, optional
        Whether to print the details of each stage (default is True)

    Returns:
    --------
    dict
        Dictionary containing lists of SWU, feed, and tailing quantities 
        for each stage
    '''
    if printing:
        print('Calculating SWU for multi-stage enrichment process:')
        print('\tFeed Enrichments:', feed_enrs)
        print('\tProduct Enrichments:', prod_enrs)
        print('\tTailing Enrichments:', tailing_enrs)
    if type(feed_enrs) == float: feed_enrs = [feed_enrs]
    if type(tailing_enrs) == float: tailing_enrs = [tailing_enrs]
    if type(prod_enrs) == float:
        # set up stages leading up to product
        if len(feed_enrs) > 1:
            prod_enrs = feed_enrs[1:] + [prod_enrs]
        else:
            prod_enrs = [prod_enrs]

    # filter out unnecessary stages
    if len(prod_enrs) < len(feed_enrs):
        final_enr = prod_enrs[-1]
        for indx, val in enumerate(feed_enrs):
            if val > final_enr:
                break
        feed_enrs = feed_enrs[:indx]
        tailing_enrs = tailing_enrs[:indx]

    assert len(feed_enrs) == len(prod_enrs) == len(tailing_enrs), f"Mismatch in number of stages: lengths of feed={len(feed_enrs)}, prod={len(prod_enrs)}, tailing={len(tailing_enrs)}." 
    assert prod_enrs[0] > feed_enrs[0] > tailing_enrs[0], f"Enrichment levels must satisfy prod > feed > tailing for the first stage: prod={prod_enrs[0]}, feed={feed_enrs[0]}, tailing={tailing_enrs[0]}."
    n_stages = len(feed_enrs)
    # check connectivity
    for n in range(n_stages-2):
        assert(prod_enrs[n] == feed_enrs[n+1])

    # check tailing consistency
    for indx, val in enumerate(tailing_enrs):
        if indx == 0: continue
        if val != tailing_enrs[0]:
            if val not in feed_enrs[:indx]:
                raise ValueError('tailing is not consistent')

    # go backwards
    swu_list = [0] * n_stages
    feed_list = [0] * n_stages
    tailing_list = [0] * n_stages
    qty_prod = [0] * n_stages
    qty_prod[-1] = 1
    # work backwards
    for n in range(n_stages)[::-1]:
        swu = qty_prod[n] * calculate_swu(feed_enrs[n], tailing_enrs[n], prod_enrs[n])
        feed = qty_prod[n] * calculate_feed(feed_enrs[n], tailing_enrs[n], prod_enrs[n])
        qty_tailing = feed - qty_prod[n]
        matches = np.isclose(feed_enrs, tailing_enrs[n], atol=1e-8)
        if np.any(matches):
            # goes to feed to a higher category
            indx = np.where(matches)[0][0]
            feed_list[indx] -= qty_tailing
            if indx != 0:
                qty_prod[indx-1] -= qty_tailing
        else:
            # goes to tails inventory
            tailing_list[n] += qty_tailing

        if printing:
            print(f'\tStage {n}:')
            print(f'\t\tProd qty: {qty_prod[n]:.6f} (enr: {prod_enrs[n]: .4%})')
            print(f'\t\tFeed qty: {feed:.6f} (enr: {feed_enrs[n]: .4%})')
            print(f'\t\tTailing qty: {qty_tailing:.6f} (enr: {tailing_enrs[n]: .4%})')
            if np.any(matches):
                print(f'\t\tSubtracting {qty_tailing:.6f} from stage {indx}')
            
        if n != 0:  
            qty_prod[n-1] += feed
        swu_list[n] += swu
        feed_list[n] += feed
        
    return {'swu': swu_list, 'feed': feed_list, 'tailing': tailing_list}