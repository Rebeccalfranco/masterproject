# -*- coding: utf-8 -*-
"""
Created on Sat Jan  7 15:35:54 2023

@author: rebec
"""

from solve_network import *

def case_selection(case):
    DE_1node = pypsa.Network("elec_s_337.nc")
    DE_1node.set_snapshots(pd.date_range('2019-01-01', periods=5, freq='H'))
    storage_map = {}
    DE_1node.lines.s_nom = 1000000
    
    from pypsa.linopt import get_var, linexpr, join_exprs, define_constraints
    
    list_renewable_carriers = ['solar', 'onwind', 'biomass', 'geothermal', 'ror', 'offwind-ac', 'hydro', 'offwind-dc', 'PHS', 'Renewable']
    
    if case=='unconstrained':
       solve_network_unconstrained(DE_1node, renewable_carriers = list_renewable_carriers) 

    if case =='co2cap':
        co2_emissions=0.6*3066
        solve_network_co2cap(DE_1node, renewable_carriers = list_renewable_carriers,co2_emissions = co2_emissions) #list_renewable_carriers

    if case=='certificates':
        renewable_Shares = pd.Series([0.8 for _ in range(len(DE_1node.snapshots))], index=DE_1node.snapshots)
        solve_network_certificates(DE_1node, renewable_shares= [0.25,0.25,0.25,0.25,0.25, 0.25], renewable_carriers = list_renewable_carriers)

    # ax = DE_1node.generators_t.p.plot()
    # DE_1node.storage_units_t.p.plot(ax=ax)
    # DE_1node.loads_t.p.plot(ax=ax)
    cap_installed = DE_1node.generators.p_nom_opt
    cap_installed_storage = DE_1node.storage_units.p_nom_opt

    production = pd.concat([DE_1node.generators_t.p, DE_1node.storage_units_t.p], axis=1)
    production_total = production.sum()
    production_share = production_total/production_total.sum()
    co2_emissions_t=np.nansum((DE_1node.snapshot_weightings.generators @ DE_1node.generators_t.p) / DE_1node.generators.efficiency * DE_1node.generators.carrier.map(DE_1node.carriers.co2_emissions))
    print("CO2 emissions",case," brown field:\n", co2_emissions_t)
    print("installed capacity:\n", cap_installed)
    print("installed storage:\n", cap_installed_storage)
    print("total production per carrier:\n", production_total)
    print("production share per carrier:\n", production_share)
    print("total load DE: ", DE_1node.loads_t.p.sum().sum())
    system_cost =DE_1node.objective/DE_1node.loads_t.p.sum().sum()    
    print("System cost [euro/MWh]", system_cost)


if __name__=="__main__":
    case = 'unconstrained'
    # case = 'co2cap'
    # case = 'certificates'
    case_selection(case)
    
    