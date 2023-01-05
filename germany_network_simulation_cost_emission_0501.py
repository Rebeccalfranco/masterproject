# -*- coding: utf-8 -*-
"""
Created on Fri Dec 23 17:54:55 2022

@author: rebec
"""

#%% “brown field” (DE Network) unconstrained

import pypsa
import pandas as pd
from pypsa.linopt import get_var, linexpr, define_constraints
import logging
logger = logging.getLogger(__name__)
import numpy as np

def solve_network(n, renewable_carriers, *args, **kwargs):
    """Solve the network.
    Args:
        n (PyPSA Network): PyPSA network to be solved.
    """
        

    def storage_restriction(n, snapshots):
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

    def storage_variables_constraints(n, snapshots):
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
        #//TODO: #6 get_var does not work for p_nom if we load a network from a file, since the variable is not defined in the network.
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

    def extra_functionalities(n, snapshots):
        storage_restriction(n,snapshots)
        storage_variables_constraints(n,snapshots)

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

    
    create_fictious_storage_units(n)

    if 'Renewable_Storage' not in renewable_carriers:
        renewable_carriers.append('Renewable_Storage')


    n.lopf(
        n.snapshots[:5],
        solver_name='gurobi',
        pyomo=False,
        extra_functionality=extra_functionalities,
    )

if __name__=="__main__":
    DE_1node = pypsa.Network("elec_s_337.nc")
    DE_1node.set_snapshots(pd.date_range('2019-01-01', periods=5, freq='H'))
    storage_map = {}
    DE_1node.lines.s_nom = 1000000

    from pypsa.linopt import get_var, linexpr, join_exprs, define_constraints

    list_renewable_carriers = ['solar', 'onwind', 'biomass', 'geothermal', 'ror', 'offwind-ac', 'hydro', 'offwind-dc', 'PHS', 'Renewable']
    solve_network(DE_1node, renewable_carriers = list_renewable_carriers) #list_renewable_carriers
    #print(DE_1node.storage_units.p_nom_opt)
    #print(DE_1node.storage_units.p_nom)

    #print(DE_1node.generators.p_nom_opt)
    
    # DE_1node.generators_t.p.plot()


    # Evaluate the share of renewable energy
    production = DE_1node.generators_t.p
    production_total = DE_1node.generators_t.p.sum()
    production_share = production_total/production_total.sum()

    # ax = DE_1node.generators_t.p.plot()
    # DE_1node.storage_units_t.p.plot(ax=ax)
    # DE_1node.loads_t.p.plot(ax=ax)

    cap_installed = DE_1node.generators.p_nom_opt
    cap_installed_storage = DE_1node.storage_units.p_nom_opt

    production = pd.concat([DE_1node.generators_t.p, DE_1node.storage_units_t.p], axis=1)
    production_total = production.sum()
    production_share = production_total/production_total.sum()
    co2_emissions_t=np.nansum((DE_1node.snapshot_weightings.generators @ DE_1node.generators_t.p) / DE_1node.generators.efficiency * DE_1node.generators.carrier.map(DE_1node.carriers.co2_emissions))
    print("CO2 emissions unconstrained brown field:\n", co2_emissions_t)
    print("installed capacity:\n", cap_installed)
    print("installed storage:\n", cap_installed_storage)
    print("total production per carrier:\n", production_total)
    print("production share per carrier:\n", production_share)
    print("total load DE: ", DE_1node.loads_t.p.sum().sum())
    system_cost =DE_1node.objective/DE_1node.loads_t.p.sum().sum()    
    print("System cost [euro/MWh]", system_cost)

#%% “brown field” constrained (CO2 cap)
import pypsa
import pandas as pd
from pypsa.linopt import get_var, linexpr, define_constraints
import logging
logger = logging.getLogger(__name__)
import numpy as np

def solve_network(n, renewable_carriers, *args, **kwargs):
    """Solve the network.
    Args:
        n (PyPSA Network): PyPSA network to be solved.
    """

    def storage_restriction(n, snapshots):
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

    def storage_variables_constraints(n, snapshots):
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
        #//TODO: #6 get_var does not work for p_nom if we load a network from a file, since the variable is not defined in the network.
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

    def extra_functionalities(n, snapshots):
        storage_restriction(n,snapshots)
        storage_variables_constraints(n,snapshots)

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
    
        
    create_fictious_storage_units(n)

    if 'Renewable_Storage' not in renewable_carriers:
        renewable_carriers.append('Renewable_Storage')     
    
    
    n.lopf(
        n.snapshots[:6],
        solver_name='gurobi',
        pyomo=False,
        extra_functionality=extra_functionalities,
    )

if __name__=="__main__":
    DE_1node = pypsa.Network("elec_s_337.nc")
    DE_1node.lines.s_nom = 1000000
    DE_1node.set_snapshots(pd.date_range('2019-01-01', periods=5, freq='H'))    
    renewable_Shares = pd.Series([0.8 for _ in range(len(DE_1node.snapshots))], index=DE_1node.snapshots)
    storage_map = {}

    from pypsa.linopt import get_var, linexpr, join_exprs, define_constraints

       

    co2_emissions=0.6*39928
    
    DE_1node.add("GlobalConstraint", "CO2Limit",
        carrier_attribute="co2_emissions", sense="<=",
        constant=co2_emissions)
           
    list_renewable_carriers =  ['Renewable','Solar', 'solar','offwind-ac', 'Wind', 'onwind', 'biomass','ror', 'geothermal','hydro', 'offwind-ac', 'offwind-dc', 'Renewable_Storage']  #['Solar','solar', 'onwind', 'biomass', 'geothermal', 'ror', 'offwind-ac', 'hydro', 'offwind-dc', 'PHS', 'Renewable_Storage','Wind']
    #PHS is a problem, no generators with PHS unfeasible solution
    #solve_network(n, renewable_shares= [0.25,1,1,1,1], renewable_carriers = ['Solar', 'solar','offwind-ac', 'Wind', 'Renewable_Storage'])
    solve_network(DE_1node, renewable_carriers = list_renewable_carriers) #list_renewable_carriers
    print(DE_1node.storage_units.p_nom_opt)
    print(DE_1node.storage_units.p_nom)

    print(DE_1node.generators.p_nom_opt)
    
    # DE_1node.generators_t.p.plot()


    # Evaluate the share of renewable energy
    production = DE_1node.generators_t.p
    production_total = DE_1node.generators_t.p.sum()
    production_share = production_total/production_total.sum()
    production_total
    production_share


    #ax = DE_1node.generators_t.p.plot()
    #DE_1node.storage_units_t.p.plot(ax=ax)
    #DE_1node.loads_t.p.plot(ax=ax)

    cap_installed = DE_1node.generators.p_nom_opt
    cap_installed_storage = DE_1node.storage_units.p_nom_opt

    production = pd.concat([DE_1node.generators_t.p, DE_1node.storage_units_t.p], axis=1)
    production_total = production.sum()
    production_share = production_total/production_total.sum()

    co2_emissions_t=np.nansum((DE_1node.snapshot_weightings.generators @ DE_1node.generators_t.p) / DE_1node.generators.efficiency * DE_1node.generators.carrier.map(DE_1node.carriers.co2_emissions))
    print("CO2 emissions CO2 cap brown field:\n", co2_emissions_t)
    print("installed capacity:\n", cap_installed)
    print("installed storage:\n", cap_installed_storage)
    print("total production per carrier:\n", production_total)
    print("production share per carrier:\n", production_share)
    print("total load DE: ", DE_1node.loads_t.p.sum().sum())
    system_cost =DE_1node.objective/DE_1node.loads_t.p.sum().sum()    
    print("System cost [euro/MWh]", system_cost)
#%% “brown field” constrained (cert.)
def solve_network(n, renewable_shares, renewable_carriers, *args, **kwargs):
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

    def storage_restriction(n, snapshots):
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

    def storage_variables_constraints(n, snapshots):
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
        #//TODO: #6 get_var does not work for p_nom if we load a network from a file, since the variable is not defined in the network.
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
            
    def extra_functionalities(n, snapshots):
        fix_bus_production(n, snapshots)
        storage_restriction(n,snapshots)
        storage_variables_constraints(n,snapshots)

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
            #temp_renewable_share.loc[:len(renewable_share)-1] = renewable_share
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

if __name__=="__main__":
      
    DE_1node = pypsa.Network("elec_s_337.nc")
    DE_1node.lines.s_nom = 1000000
    DE_1node.set_snapshots(pd.date_range('2019-01-01', periods=5, freq='H'))
    renewable_Shares = pd.Series([0.8 for _ in range(len(DE_1node.snapshots))], index=DE_1node.snapshots)
    storage_map = {}

    from pypsa.linopt import get_var, linexpr, join_exprs, define_constraints

    list_renewable_carriers =  ['Solar', 'solar','offwind-ac', 'Wind', 'onwind', 'biomass','ror', 'geothermal','hydro', 'offwind-ac', 'offwind-dc', 'Renewable_Storage']  #['Solar','solar', 'onwind', 'biomass', 'geothermal', 'ror', 'offwind-ac', 'hydro', 'offwind-dc', 'PHS', 'Renewable_Storage','Wind']
    solve_network(DE_1node, renewable_shares= [0.25,0.25,0.25,0.25,0.25, 0.25], renewable_carriers = list_renewable_carriers)

    # DE_1node.generators_t.p.plot()
    
    
    # Evaluate the share of renewable energy
    production = DE_1node.generators_t.p
    production_total = DE_1node.generators_t.p.sum()
    production_share = production_total/production_total.sum()
    production_total
    production_share
    
    
    # ax = DE_1node.generators_t.p.plot()
    # DE_1node.storage_units_t.p.plot(ax=ax)
    # DE_1node.loads_t.p.plot(ax=ax)
    
    cap_installed = DE_1node.generators.p_nom_opt
    cap_installed_storage = DE_1node.storage_units.p_nom_opt
    
    production = pd.concat([DE_1node.generators_t.p, DE_1node.storage_units_t.p], axis=1)
    production_total = production.sum()
    production_share = production_total/production_total.sum()
    
    co2_emissions_t=np.nansum((DE_1node.snapshot_weightings.generators @ DE_1node.generators_t.p) / DE_1node.generators.efficiency * DE_1node.generators.carrier.map(DE_1node.carriers.co2_emissions))
    print("CO2 emissions unconstrained brown field:\n", co2_emissions_t)
    print("installed capacity:\n", cap_installed)
    print("installed storage:\n", cap_installed_storage)
    print("total production per carrier:\n", production_total)
    print("production share per carrier:\n", production_share)
    print("total load DE: ", DE_1node.loads_t.p.sum().sum())
    system_cost =DE_1node.objective/DE_1node.loads_t.p.sum().sum()    
    print("System cost [euro/MWh]", system_cost)