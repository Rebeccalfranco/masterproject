# -*- coding: utf-8 -*-
"""
Created on Fri Jan  6 18:36:04 2023

@author: rebec
"""

import pypsa
import pandas as pd
from pypsa.linopt import get_var, linexpr, define_constraints
import logging
import numpy as np

logger = logging.getLogger(__name__)

def storage_restriction(n, snapshots,renewable_carriers):
    """Define the constraint that ensure that energy generated by renewable resources that has been stored in storage units a
    fictious storage unit was added for each normal storage unit that would only allow charging using generation units with 
    the carrier "Renewable" (this is defined in the function storage_restriction(n,snapshots)).

    Args:
        n (PyPSA Network): PyPSA network to which the constraint is added.
        snapshots (list or pandas.Index): List of snapshots or time steps. All time-dependent series quantities are indexed by network.snapshots.
    """

    renewable_generators = n.generators[n.generators.carrier.isin(renewable_carriers)].index
    renewable_storage_units = n.storage_units[n.storage_units.carrier.isin(renewable_carriers)].index
    storage_units  = n.storage_units[~(n.storage_units.carrier.isin(renewable_carriers))].index

    renewable_generators_feed_in = (linexpr((1, get_var(n, "Generator", "p")[renewable_generators]))).sum(axis=1)
    renewable_storage_units_store = (linexpr((1, get_var(n, "StorageUnit", "p_store")[renewable_storage_units]))).sum(axis=1)
    renewable_storage_units_dispatch = (linexpr((1, get_var(n, "StorageUnit", "p_dispatch")[renewable_storage_units]))).sum(axis=1)

    define_constraints(
        n, renewable_generators_feed_in +renewable_storage_units_store, ">=", 0, "Generator", "restrict_renewable_storages_share"
    )

def storage_variables_constraints(n, snapshots,renewable_carriers):
    """Define the constraint that coupple the fictious and real storage variables together
    To ensure the fictious storage units do not extent the normal (conventional) storage units or 
    in other words provide more storage possibility to the system and stay purely fictious, the optimization
    variables of the normal (conventional) storage units and the fictious storage units are coupled. 
    This means that the sum of both storage units (fictious + conventional) is limited by the maximum/minimum
    properties of the corresponding normal storage unit.

    Args:
        n (PyPSA Network): PyPSA network to which the constraint is added.
        snapshots (list or pandas.Index): List of snapshots or time steps. All time-dependent series quantities are indexed by network.snapshots.
    """    
    renewable_storage_units = n.storage_units[n.storage_units.carrier.isin(renewable_carriers)].index
    renewable_storage_units_ext = n.storage_units[n.storage_units.carrier.isin(renewable_carriers) & n.storage_units.p_nom_extendable].index
    storage_units  = n.storage_units[~(n.storage_units.carrier.isin(renewable_carriers))].index
    storage_units_ext = n.storage_units[~(n.storage_units.carrier.isin(renewable_carriers)) & n.storage_units.p_nom_extendable].index
    storage_units_non_ext = n.storage_units[~(n.storage_units.carrier.isin(renewable_carriers)) & ~(n.storage_units.p_nom_extendable)].index

    renewable_storage_units_store = (linexpr((1, get_var(n, "StorageUnit", "p_store")[renewable_storage_units])))
    storage_units_store = (linexpr((1, get_var(n, "StorageUnit", "p_store")[storage_units])))

    renewable_storage_units_dispatch = (linexpr((1, get_var(n, "StorageUnit", "p_dispatch")[renewable_storage_units])))
    storage_units_dispatch = (linexpr((1, get_var(n, "StorageUnit", "p_dispatch")[storage_units]))) 

    renewable_storage_units_soc = (linexpr((1, get_var(n, "StorageUnit", "state_of_charge")[renewable_storage_units])))
    storage_units_soc = (linexpr((1, get_var(n, "StorageUnit", "state_of_charge")[storage_units])))
    storage_units_store_max_non_ext = (linexpr((-1, (n.storage_units.p_nom*n.storage_units.p_max_pu)[storage_units_non_ext])))
    try:
        storage_units_store_max_ext = (linexpr((-1, (get_var(n, "StorageUnit", "p_nom")*n.storage_units.p_max_pu)[storage_units_ext])))
        storage_units_dispatch_max_ext = (linexpr((-1, (get_var(n, "StorageUnit", "p_nom")*n.storage_units.p_min_pu)[storage_units_ext])))
        storage_units_soc_max_ext = (linexpr((-n.storage_units.max_hours[storage_units_ext], (get_var(n, "StorageUnit", "p_nom"))[storage_units_ext])))
    except KeyError:
        storage_units_store_max_ext = None
        storage_units_dispatch_max_ext = None
        storage_units_soc_max_ext = None

    storage_units_dispatch_max_non_ext = (linexpr((-1, (n.storage_units.p_nom*n.storage_units.p_min_pu)[storage_units_non_ext])))
    storage_units_soc_max_non_ext = (linexpr((-n.storage_units.max_hours[storage_units_non_ext], (n.storage_units.p_nom)[storage_units_non_ext])))

    try:
        renewable_storage_units_extension = (linexpr((1, (get_var(n, "StorageUnit", "p_nom"))[renewable_storage_units_ext])))
        storage_units_extension = (linexpr((-1, (get_var(n, "StorageUnit", "p_nom"))[storage_units_ext])))
    except KeyError:
        logger.warning("No storage unit extension is allowed.")

    for s, name in enumerate(storage_units):
        if name in storage_units_ext:
            define_constraints(
                n, renewable_storage_units_store[renewable_storage_units[s]] + storage_units_store[storage_units[s]] + storage_units_store_max_ext[storage_units[s]], "<=", 0, "StorageUnit", "max_store"
                )

            define_constraints(
                n, renewable_storage_units_dispatch[renewable_storage_units[s]] + storage_units_dispatch[storage_units[s]] + storage_units_dispatch_max_ext[storage_units[s]], "<=", 0, "StorageUnit", "max_dispatch"
                )

            define_constraints(
                n,  storage_units_soc_max_ext[storage_units[s]] + renewable_storage_units_soc[renewable_storage_units[s]] + storage_units_soc[storage_units[s]], "<=", 0, "StorageUnit", "state_of_charge_restriction"
                )
            define_constraints(
                n, renewable_storage_units_extension[renewable_storage_units[s]] + storage_units_extension[storage_units[s]], "==", 0, "StorageUnit", "storage_extension"
                )
        else:
            define_constraints(
                n, renewable_storage_units_store[renewable_storage_units[s]] + storage_units_store[storage_units[s]] + storage_units_store_max_non_ext[storage_units[s]], "<=", 0, "StorageUnit", "max_store"
                )

            define_constraints(
                n, renewable_storage_units_dispatch[renewable_storage_units[s]] + storage_units_dispatch[storage_units[s]] + storage_units_dispatch_max_non_ext[storage_units[s]], "<=", 0, "StorageUnit", "max_dispatch"
                )

            define_constraints(
                n,  storage_units_soc_max_non_ext[storage_units[s]] + renewable_storage_units_soc[renewable_storage_units[s]] + storage_units_soc[storage_units[s]], "<=", 0, "StorageUnit", "state_of_charge_restriction"
                )
            
def create_fictious_storage_units(n):
    """Create fictious storage units for each storage unit.
    The fictious storage units are created in order to be able to model the share of renewable storage units in the system.
    The share of renewable storage units is defined by the user and is used to limit the share of renewable storage units in the system.
    Args:
        n (PyPSA Network): PyPSA network to which the new storage units are added.
    """    
    n.madd('StorageUnit',
        n.storage_units.index,
        suffix='_Renewable',
        carrier='Renewable_Storage',
        **n.storage_units.drop('carrier', axis=1))

def solve_network_unconstrained(n, renewable_carriers, *args, **kwargs):
    """Solve the network.
    Args:
        n (PyPSA Network): PyPSA network to be solved.
        """           
    def extra_functionalities(n, snapshots):
        storage_restriction(n,snapshots,renewable_carriers)
        storage_variables_constraints(n,snapshots,renewable_carriers)
    
    create_fictious_storage_units(n)

    if 'Renewable_Storage' not in renewable_carriers:
        renewable_carriers.append('Renewable_Storage')


    n.lopf(
        n.snapshots[:6],
        solver_name='gurobi',
        pyomo=False,
        extra_functionality=extra_functionalities,
    )

def solve_network_co2cap(n, renewable_carriers,co2_emissions, *args, **kwargs):
    """Solve the network.
    Args:
        n (PyPSA Network): PyPSA network to be solved.
    """

    def extra_functionalities(n, snapshots):
        storage_restriction(n,snapshots,renewable_carriers)
        storage_variables_constraints(n,snapshots,renewable_carriers)  
        
    create_fictious_storage_units(n)

    if 'Renewable_Storage' not in renewable_carriers:
        renewable_carriers.append('Renewable_Storage')   
    
    n.add("GlobalConstraint", "CO2Limit",carrier_attribute="co2_emissions", sense="<=", constant=co2_emissions)
    
    n.lopf(
        n.snapshots[:6],
        solver_name='gurobi',
        pyomo=False,
        extra_functionality=extra_functionalities,
    )

def solve_network_certificates(n, renewable_shares, renewable_carriers, *args, **kwargs):
    """Solve the network.
    Args:
        n (PyPSA Network): PyPSA network to be solved.
    """
    def fix_bus_production(n, snapshots):
        """Define the constraint that the sum of the renewable generation in each snapshot must be equal to the minimum required renewable share.

        Args:
            n (PyPSA Network): PyPSA network to which the constraint is added.
            snapshots (list or pandas.Index): List of snapshots or time steps. All time-dependent series quantities are indexed by network.snapshots.
        """

        demand_at_t = n.loads_t.p_set.loc[snapshots].sum(axis=1)

        renewable_generators = n.generators[n.generators.carrier.isin(renewable_carriers)].index
        renewable_storage_units = n.storage_units[n.storage_units.carrier.isin(renewable_carriers)].index
        renewable_storage_units_store = (linexpr((-1, get_var(n, "StorageUnit", "p_store")[renewable_storage_units]))).sum(axis=1)
        
        renewable_generation = (linexpr((1, get_var(n, "StorageUnit", "p_dispatch")[renewable_storage_units]))).sum(axis=1) + (linexpr((1, get_var(n, "Generator", "p")[renewable_generators]))).sum(axis=1)
        
        define_constraints(
            n, renewable_generation + renewable_storage_units_store, ">=", demand_at_t *renewable_shares , "Generator", "production_share"
        )    
            
    def extra_functionalities(n, snapshots):
        fix_bus_production(n, snapshots)
        storage_restriction(n,snapshots,renewable_carriers)
        storage_variables_constraints(n,snapshots,renewable_carriers)

    def define_RE_share(n, renewable_share):
        """Define the share of renewable storage units in the system. and check if the length of the share is equal to the number of snapshots, 
        and has similar index as the snapshots."""
        if len(renewable_share) > len(n.snapshots):
            logger.warning(
                "The length of passed renewable share per snapshots is greater than the number of snapshots."
                )
            logger.warning(
                f"Only taking the first {len(n.snapshots)} values."
            )
            temp_renewable_share = pd.Series(renewable_share[:len(n.snapshots)], index=n.snapshots)
        elif len(renewable_share) < len(n.snapshots):
            logger.warning(
                "The length of passed renewable share per snapshots is less than the number of snapshots."
                )
            logger.warning("Filling the missing values with 0s.")
            temp_renewable_share = pd.Series(0, index=n.snapshots)
            temp_renewable_share[:len(renewable_share)] = pd.Series(renewable_share, index=n.snapshots[:len(renewable_share)])
        else:
            temp_renewable_share = pd.Series(renewable_share, index=n.snapshots)

        return temp_renewable_share

    renewable_shares = define_RE_share(n, renewable_shares)

    create_fictious_storage_units(n)

    if 'Renewable_Storage' not in renewable_carriers:
        renewable_carriers.append('Renewable_Storage')
        
    
    n.lopf(
        n.snapshots[:6],
        solver_name='gurobi',
        pyomo=False,
        extra_functionality=extra_functionalities,
    )

