# -*- coding: utf-8 -*-
"""
Created on Sat Jan  7 16:02:33 2023

@author: rebec
"""

from solve_network import *

def case_selection(case):
    DE_1node = pypsa.Network()
    DE_1node.set_snapshots(pd.date_range('2019-01-01', periods=5, freq='H'))
    snapshot = 5
    load= 40000
    # Create carriers for which CO2 emissions unequal 0
    co2_emissions_coal=0.34
    DE_1node.add('Carrier', 'Coal', co2_emissions = co2_emissions_coal)

    DE_1node.add('Bus','DE')

    DE_1node.add('Generator', 'Solar', bus = 'DE', carrier='Renewable', p_max_pu=[1, 0, 0, 0, 0], p_nom = 0, marginal_cost=0.010, capital_cost=35602, p_nom_extendable=True)
    DE_1node.add('Generator', 'Wind', bus = 'DE', carrier='Renewable', p_max_pu=[1, 0, 0, 0, 0], p_nom = 0, marginal_cost=0.015, capital_cost=96085, p_nom_extendable=True)

    DE_1node.add('StorageUnit', 'Storage_1', bus='DE', carrier='Others', p_nom=0, max_hours=5,marginal_cost=1,capital_cost=177345, p_nom_extendable=True)

    DE_1node.add('StorageUnit', 'Storage_2', bus='DE', carrier='Others', p_nom=0, max_hours=5, marginal_cost=1,capital_cost=177345, p_nom_extendable=True)


    DE_1node.add('Generator', 'Coal', bus = 'DE', carrier='Coal', p_nom = 14830, marginal_cost=28.197, capital_cost=349977)

    DE_1node.add('Load', 'DE_Load', bus='DE', p_set = [load for _ in range(snapshot)])

    storage_map = {}    
    
    list_renewable_carriers =  ['Renewable','Solar', 'solar','offwind-ac', 'Wind', 'onwind', 'biomass','ror', 'geothermal','hydro', 'offwind-ac', 'offwind-dc', 'Renewable_Storage']  #['Solar','solar', 'onwind', 'biomass', 'geothermal', 'ror', 'offwind-ac', 'hydro', 'offwind-dc', 'PHS', 'Renewable_Storage','Wind']
    if case=='unconstrained':
       solve_network_unconstrained(DE_1node, renewable_carriers = list_renewable_carriers) 

    if case =='co2cap':
        co2_emissions=0.6*3066
        solve_network_co2cap(DE_1node, renewable_carriers = list_renewable_carriers,co2_emissions = co2_emissions) #list_renewable_carriers

    if case=='certificates':
        renewable_Shares = pd.Series([0.75 for _ in range(len(DE_1node.snapshots))], index=DE_1node.snapshots)
        # renewable_shares= [0.25,0.25,0.25,0.25,0.25, 0.25]
        solve_network_certificates(DE_1node, renewable_shares= renewable_Shares, renewable_carriers = list_renewable_carriers)
    DE_1node.generators_t.p.plot()


    # Evaluate the share of renewable energy
    production = DE_1node.generators_t.p
    production_total = DE_1node.generators_t.p.sum()
    production_share = production_total/production_total.sum()

    ax = DE_1node.generators_t.p.plot()
    DE_1node.storage_units_t.p.plot(ax=ax)
    DE_1node.loads_t.p.plot(ax=ax)

    cap_installed = DE_1node.generators.p_nom_opt
    cap_installed_storage = DE_1node.storage_units.p_nom_opt

    production = pd.concat([DE_1node.generators_t.p, DE_1node.storage_units_t.p], axis=1)
    production_total = production.sum()
    production_share = production_total/production_total.sum()
    co2_emissions_t=np.nansum((DE_1node.snapshot_weightings.generators @ DE_1node.generators_t.p) / DE_1node.generators.efficiency * DE_1node.generators.carrier.map(DE_1node.carriers.co2_emissions))
    print("CO2 emissions",case,"green field:\n", co2_emissions_t)
    print("installed capacity:\n", cap_installed)
    print("installed storage:\n", cap_installed_storage)
    print("total production per carrier:\n", production_total)
    print("production share per carrier:\n", production_share)
    system_cost =DE_1node.objective/(snapshot*load)    
    print("System cost [euro/MWh]", system_cost)
    
    

if __name__=="__main__":
    # case = 'unconstrained'
    # case = 'co2cap'
    case = 'certificates'
    case_selection(case)