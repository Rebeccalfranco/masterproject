# -*- coding: utf-8 -*-
"""
Created on Sat Jan  7 15:35:54 2023

@author: rebec
"""
#%%

from solve_network import *

def case_selection(case):
    DE_1node = pypsa.Network("elec_s_337.nc")
    DE_1node.lines.s_nom = 1000000
    DE_1node.set_snapshots(pd.date_range('2019-01-01', periods=5, freq='H'))
    storage_map = {}
    
    
    from pypsa.linopt import get_var, linexpr, join_exprs, define_constraints
    
    list_renewable_carriers =  ['solar','offwind-ac', 'onwind', 'biomass','ror', 'geothermal','hydro', 'offwind-ac', 'offwind-dc', 'Renewable_Storage']  #['Solar','solar', 'onwind', 'biomass', 'geothermal', 'ror', 'offwind-ac', 'hydro', 'offwind-dc', 'PHS', 'Renewable_Storage','Wind']
        
    if case=='unconstrained':
       solve_network_unconstrained(DE_1node, renewable_carriers = list_renewable_carriers) 

    if case =='co2cap':
        co2_emissions=0*7319
        solve_network_co2cap(DE_1node, renewable_carriers = list_renewable_carriers,co2_emissions = co2_emissions) #list_renewable_carriers

    if case=='certificates':
        renewable_Shares = pd.Series([0.25 for _ in range(len(DE_1node.snapshots))], index=DE_1node.snapshots)
        solve_network_certificates(DE_1node, renewable_shares= renewable_Shares, renewable_carriers = list_renewable_carriers)

   
    
    # generic_generators =['coal','CCGT','solar', 'onwind', 'biomass', 'geothermal', 'ror', 'offwind-ac', 'hydro', 'offwind-dc', 'PHS', 'Renewable', 'oil','OCGT','nuclear', 'lignite'
    p_sum_solar=p_sum_onwind= p_sum_coal = p_sum_ccgt  = p_sum_biomass =p_sum_geothermal = p_sum_ror =p_sum_offwindac=p_sum_hydro =p_sum_phs =p_sum_offwinddc= p_sum_oil =p_sum_ocgt= p_sum_nuclear =p_sum_lignite =p_sum_renewable =0
    for i in range(len(DE_1node.generators)):
        
        if DE_1node.generators.carrier.isin(['solar'])[i] == True:            
            index_solar = DE_1node.generators.index[i]
            p_sum_solar = p_sum_solar + DE_1node.generators_t.p[index_solar]            
        elif DE_1node.generators.carrier.isin(['onwind'])[i] == True:            
            index_onwind = DE_1node.generators.index[i]
            p_sum_onwind = p_sum_onwind + DE_1node.generators_t.p[index_onwind]
        elif DE_1node.generators.carrier.isin(['coal'])[i] == True:            
            index_coal = DE_1node.generators.index[i]
            p_sum_coal = p_sum_coal + DE_1node.generators_t.p[index_coal]
        elif DE_1node.generators.carrier.isin(['CCGT'])[i] == True:            
            index_ccgt = DE_1node.generators.index[i]
            p_sum_ccgt = p_sum_ccgt + DE_1node.generators_t.p[index_ccgt]
        elif DE_1node.generators.carrier.isin(['biomass'])[i] == True:            
            index_biomass = DE_1node.generators.index[i]
            p_sum_biomass = p_sum_biomass + DE_1node.generators_t.p[index_biomass]
        # elif DE_1node.generators.carrier.isin(['geothermal'])[i] == True:            
        #     index_geothermal = DE_1node.generators.index[i]
        #     p_sum_geothermal = p_sum_geothermal + DE_1node.generators_t.p[index_geothermal]
        elif DE_1node.generators.carrier.isin(['ror'])[i] == True:            
            index_ror = DE_1node.generators.index[i]
            p_sum_ror = p_sum_ror + DE_1node.generators_t.p[index_ror]
        elif DE_1node.generators.carrier.isin(['offwind-ac'])[i] == True:            
            index_offwindac = DE_1node.generators.index[i]
            p_sum_offwindac = p_sum_offwindac + DE_1node.generators_t.p[index_offwindac]
        elif DE_1node.generators.carrier.isin(['offwind-dc'])[i] == True:            
            index_offwinddc = DE_1node.generators.index[i]
            p_sum_offwinddc = p_sum_offwinddc + DE_1node.generators_t.p[index_offwinddc]
        elif DE_1node.generators.carrier.isin(['oil'])[i] == True:            
            index_oil = DE_1node.generators.index[i]
            p_sum_oil = p_sum_oil + DE_1node.generators_t.p[index_oil]
        elif DE_1node.generators.carrier.isin(['OCGT'])[i] == True:            
            index_ocgt = DE_1node.generators.index[i]
            p_sum_ocgt = p_sum_ocgt + DE_1node.generators_t.p[index_ocgt]
        elif DE_1node.generators.carrier.isin(['nuclear'])[i] == True:            
            index_nuclear = DE_1node.generators.index[i]
            p_sum_nuclear = p_sum_nuclear + DE_1node.generators_t.p[index_nuclear]
        elif DE_1node.generators.carrier.isin(['lignite'])[i] == True:            
            index_lignite = DE_1node.generators.index[i]
            p_sum_lignite = p_sum_lignite + DE_1node.generators_t.p[index_lignite]
        i=i+1
        
    for j in range(len(DE_1node.storage_units)):   
        if DE_1node.storage_units.carrier.isin(['hydro'])[j] == True:            
            index_hydro = DE_1node.storage_units.index[j]
            p_sum_hydro = p_sum_hydro + DE_1node.storage_units_t.p[index_hydro]
        elif DE_1node.storage_units.carrier.isin(['PHS'])[j] == True:            
            index_phs = DE_1node.storage_units.index[j]
            p_sum_phs = p_sum_phs + DE_1node.storage_units_t.p[index_phs]
        elif DE_1node.storage_units.carrier.isin(['Renewable_Storage'])[j] == True:            
            index_renewable = DE_1node.storage_units.index[j]
            p_sum_renewable = p_sum_renewable + DE_1node.storage_units_t.p[index_renewable]
        j=j+1
    
    production_total = pd.DataFrame()
    production_total['Combined Solar'] = p_sum_solar
    production_total['Combined Wind'] = p_sum_onwind
    production_total['Combined coal'] = p_sum_coal
    production_total['Combined ccgt'] = p_sum_ccgt
    production_total['Combined biomass'] = p_sum_biomass
    production_total['Combined ror'] = p_sum_ror
    production_total['Combined offwindac'] = p_sum_offwindac
    production_total['Combined offwinddc'] = p_sum_offwinddc
    production_total['Combined oil'] = p_sum_oil
    production_total['Combined OCGT'] = p_sum_ocgt
    production_total['Combined nuclear'] = p_sum_nuclear
    production_total['Combined lignite'] = p_sum_lignite    
    # production_total['Combined geothermal'] = p_sum_geothermal
    storage_units_total =pd.DataFrame()
    storage_units_total['Combined hydro'] = p_sum_hydro
    storage_units_total['Combined PHS'] = p_sum_phs
    storage_units_total['Combined Renewable'] = p_sum_renewable
    
    # DE_1node.generators_t.p.plot()
    production_total.plot()
    # ax = production_total.plot()
    storage_units_total.plot()
    # DE_1node.storage_units_t.p.plot()
    
    # loads_total.p.plot(ax=ax)
    # DE_1node.loads_t.p.plot()
    
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
    # case = 'unconstrained'
    # case = 'co2cap'
    case = 'certificates'
    case_selection(case)
    
    